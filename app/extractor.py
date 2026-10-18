import json #load config and save records as jsonl
import re #extract fields from html

from datetime import datetime #convert dates to yyyy-mm-dd
from html import unescape #decode html entities
from pathlib import Path #read html files


class Extractor:

    #labels and their values in the movie info section
    INFO_RE = re.compile(
        r'<rt-text[^>]*data-qa="item-label"[^>]*>(.*?)</rt-text>'
        r'\s*</dt>\s*<dd[^>]*>(.*?)</dd>',
        re.IGNORECASE | re.DOTALL
    )

    #individual values, without comma separators
    VALUE_RE = re.compile(
        r'<(rt-link|rt-text)[^>]*data-qa="item-value"[^>]*>(.*?)</\1>',
        re.IGNORECASE | re.DOTALL
    )

    #structured movie data inside html
    JSONLD_RE = re.compile(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        re.IGNORECASE | re.DOTALL
    )

    def __init__(self, config_path):
        #paths are relative to config.json
        with open(config_path, encoding="utf-8") as file:
            config = json.load(file)

        directory = Path(config_path).resolve().parent
        self.raw_data_dir = directory / config["raw_data_dir"]
        self.output_path = directory / config["extracted_file"]

    def clean_text(self, value):
        #remove tags, decode entities and join whitespace
        value = re.sub(r"<[^>]+>", " ", value)
        return " ".join(unescape(value).split())

    def find_text(self, pattern, html):
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match:
            return self.clean_text(match.group(1)) or None
        return None

    def extract_url(self, html, source_file):
        match = re.search(r'<link rel="canonical" href="([^"]+)"', html)
        if match:
            return unescape(match.group(1)).strip()

        print("[ERROR] Missing canonical URL:", source_file)
        return None

    def parse_date(self, value):
        #ignore text such as Wide or Limited after the date
        match = re.search(r"[A-Za-z]{3} \d{1,2}, \d{4}", value or "")
        if match:
            try:
                return datetime.strptime(match.group(), "%b %d, %Y").date().isoformat()
            except ValueError:
                pass
        return None

    def parse_runtime(self, value):
        #2h 28m -> 148, 2h -> 120, 57m -> 57
        parts = re.findall(r"(\d+)(h|m)", value or "")
        if not parts:
            return None

        minutes = 0
        for number, unit in parts:
            if unit == "h":
                minutes += int(number) * 60
            else:
                minutes += int(number)
        return minutes

    def extract(self, html, source_file):
        info = {}
        for label, block in self.INFO_RE.findall(html):
            values = [self.clean_text(value) for tag, value in self.VALUE_RE.findall(block)]
            #keep unique nonempty values in their original order
            info[self.clean_text(label)] = list(dict.fromkeys(v for v in values if v))

        def first(label):
            values = info.get(label, [])
            return values[0] if values else None

        #only inspect the main movie header
        hero = re.search(r"<media-hero[^>]*>(.*?)</media-hero>", html, re.IGNORECASE | re.DOTALL)
        hero_html = hero.group(1) if hero else ""
        title = self.find_text(
            r'<rt-text[^>]*slot="title"[^>]*>(.*?)</rt-text>', hero_html
        )

        #synopsis is in movie info, outside the header
        synopsis = self.find_text(
            r'<rt-text[^>]*data-qa="synopsis-value"[^>]*>(.*?)</rt-text>', html
        )

        theaters = self.parse_date(first("Release Date (Theaters)"))
        streaming = self.parse_date(first("Release Date (Streaming)"))

        #the header year can differ from the local release date
        year = None
        props = re.findall(
            r'<rt-text[^>]*slot="metadata-prop"[^>]*>(.*?)</rt-text>',
            hero_html, re.IGNORECASE | re.DOTALL
        )
        for prop in props:
            match = re.search(r"\b\d{4}\b", self.clean_text(prop))
            if match:
                year = int(match.group())
                break
        if year is None and (theaters or streaming):
            year = int((theaters or streaming)[:4])

        #read actor names from json-ld
        actors = []
        for block in self.JSONLD_RE.findall(html):
            try:
                data = json.loads(block)
            except json.JSONDecodeError:
                continue

            if isinstance(data, dict) and data.get("@type") == "Movie":
                for actor in data.get("actor", []):
                    name = actor["name"]
                    if name not in actors:
                        actors.append(name)
                break

        #audience score is stored in the audienceScore object
        popcornmeter = None
        match = re.search(r'"audienceScore":\{[^}]*"score":"(\d+)"', html)
        if match:
            value = int(match.group(1))
            if 0 <= value <= 100:
                popcornmeter = value

        #keep only the rating, without the explanation in brackets
        rating = first("Rating")
        if rating:
            rating = rating.split("(", 1)[0].strip() or None

        return {
            "url": self.extract_url(html, source_file),
            "title": title,
            "synopsis": synopsis,
            "directors": info.get("Director", []),
            "actors": actors,
            "producers": info.get("Producer", []),
            "screenwriters": info.get("Screenwriter", []),
            "genres": info.get("Genre", []),
            "release_date_theaters": theaters,
            "release_date_streaming": streaming,
            "year": year,
            "runtime_minutes": self.parse_runtime(first("Runtime")),
            "content_rating": rating,
            "popcornmeter": popcornmeter,
            "production_companies": info.get("Production Co", []),
            "original_language": first("Original Language"),
            "source_file": Path(source_file).name
        }


def remove_duplicates(output_path):
    seen = {}
    movies = []
    removed = 0

    with output_path.open(encoding="utf-8") as file:
        for line in file:
            movie = json.loads(line)
            url = movie["url"]
            #source filename can differ for the same movie
            data = {key: value for key, value in movie.items() if key != "source_file"}

            if url:
                if url in seen:
                    if data in seen[url]:
                        removed += 1
                        continue
                    print("[ERROR] Same canonical URL with different data:", url)
                else:
                    seen[url] = []
                seen[url].append(data)

            movies.append(movie)

    #rewrite jsonl with the remaining records
    with output_path.open("w", encoding="utf-8") as file:
        for movie in movies:
            file.write(json.dumps(movie, ensure_ascii=False) + "\n")

    print(f"[DEDUPLICATED] Removed {removed} records")
    return len(movies)


def main():
    config_path = Path(__file__).with_name("config.json")
    extractor = Extractor(config_path)
    files = sorted(extractor.raw_data_dir.glob("*.html"))
    if not files:
        raise SystemExit(f"No HTML files found in {extractor.raw_data_dir}")

    extractor.output_path.parent.mkdir(parents=True, exist_ok=True)

    #one record per source file, same canonical url can occur more than once
    with extractor.output_path.open("w", encoding="utf-8") as output:
        for count, path in enumerate(files, start=1):
            html = path.read_text(encoding="utf-8")
            movie = extractor.extract(html, path.name)
            output.write(json.dumps(movie, ensure_ascii=False) + "\n")
            if count % 1000 == 0:
                print(f"[EXTRACTED] {count}/{len(files)}")

    count = remove_duplicates(extractor.output_path)
    print(f"[DONE] {count} records -> {extractor.output_path}")


if __name__ == "__main__":
    main()
