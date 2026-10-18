import json #load index and movies
import math #logarithm and vector norms

from collections import Counter #query term frequencies
from pathlib import Path #paths relative to config.json

from indexer import tokenize #same tokens as in the index


class Searcher:

    def __init__(self, config_path, idf_method):
        with open(config_path, encoding="utf-8") as file:
            config = json.load(file)

        directory = Path(config_path).resolve().parent
        with (directory / config["index_file"]).open(encoding="utf-8") as file:
            self.index = json.load(file)
        with (directory / config["extracted_file"]).open(encoding="utf-8") as file:
            self.movies = [json.loads(line) for line in file]

        count = self.index["document_count"]
        self.idf = {}
        self.document_norms = [0.0] * count

        #calculate idf and full document norms once
        for term, entry in self.index["terms"].items():
            df = entry["df"]
            if idf_method == "classic":
                self.idf[term] = math.log(count / df)
            else:
                self.idf[term] = 1 + math.log((count + 1) / (df + 1))

            for document_id, tf in entry["postings"].items():
                weight = tf * self.idf[term]
                self.document_norms[int(document_id)] += weight ** 2

        self.document_norms = [math.sqrt(value) for value in self.document_norms]

    def search(self, query, scoring):
        query_weights = {}
        for term, tf in Counter(tokenize(query)).items():
            if term in self.idf:
                query_weights[term] = tf * self.idf[term]

        #only documents from query term postings are candidates
        scores = {}
        for term, query_weight in query_weights.items():
            for document_id, tf in self.index["terms"][term]["postings"].items():
                document_id = int(document_id)
                document_weight = tf * self.idf[term]
                scores[document_id] = scores.get(document_id, 0.0) + query_weight * document_weight

        if scoring in ("cosine", "cosine_popcornmeter"):
            query_norm = math.sqrt(sum(weight ** 2 for weight in query_weights.values()))
            if query_norm == 0:
                return []

            for document_id in list(scores):
                norm = query_norm * self.document_norms[document_id]
                if norm:
                    scores[document_id] /= norm
                else:
                    del scores[document_id]

        #boost text similarity using popcornmeter, if available
        if scoring == "cosine_popcornmeter":
            for document_id in scores:
                popcornmeter = self.movies[document_id]["popcornmeter"]
                if popcornmeter is not None:
                    scores[document_id] *= 1 + popcornmeter / 100

        return sorted(scores.items(), key=lambda item: item[1], reverse=True)[:10]


def main():
    config_path = Path(__file__).with_name("config.json")

    while True:
        idf_choice = input(
            "\nIDF:\n"
            "1 - classic: log(N / df)\n"
            "2 - smooth: 1 + log((N + 1) / (df + 1))\n"
            "Choice: "
        ).strip()
        scoring_choice = input(
            "\nScoring:\n"
            "1 - overlap: sum(query TF-IDF * document TF-IDF)\n"
            "2 - cosine: overlap / (query norm * document norm)\n"
            "3 - cosine + popcornmeter: cosine * (1 + popcornmeter / 100)\n"
            "Choice: "
        ).strip()
        if idf_choice not in ("1", "2") or scoring_choice not in ("1", "2", "3"):
            print("Invalid choice")
            continue

        idf_method = "classic" if idf_choice == "1" else "smooth"
        if scoring_choice == "1":
            scoring = "overlap"
        elif scoring_choice == "2":
            scoring = "cosine"
        else:
            scoring = "cosine_popcornmeter"

        query = input("\nQuery: ").strip()
        print()
        if not query:
            break

        searcher = Searcher(config_path, idf_method)

        results = searcher.search(query, scoring)
        if not results:
            print("No results")

        for rank, (document_id, score) in enumerate(results, start=1):
            movie = searcher.movies[document_id]
            print(f"{rank}. ID: {document_id} | {movie['title']} | year: {movie['year']}"
                  f" | popcornmeter: {movie['popcornmeter']} | score: {score:.6f}")
            print(movie["url"])
            print()


if __name__ == "__main__":
    main()
