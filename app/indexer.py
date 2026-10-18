import json #load movies and save index
import re #split text into tokens

from collections import Counter #count tokens in a document
from pathlib import Path #paths relative to config.json


def tokenize(text):
    #lowercase letters and numbers, without underscores
    return re.findall(r"[^\W_]+", text.lower())


class Indexer:

    def __init__(self, config_path):
        with open(config_path, encoding="utf-8") as file:
            config = json.load(file)

        directory = Path(config_path).resolve().parent
        self.input_path = directory / config["extracted_file"]
        self.output_path = directory / config["index_file"]

    def build(self):
        index = {"document_count": 0, "terms": {}}

        with self.input_path.open(encoding="utf-8") as file:
            for document_id, line in enumerate(file):
                movie = json.loads(line)
                text = (movie["title"] or "") + " " + (movie["synopsis"] or "")
                frequencies = Counter(tokenize(text))

                for term, tf in frequencies.items():
                    if term not in index["terms"]:
                        index["terms"][term] = {"df": 0, "postings": {}}

                    #each term is counted once per document for df
                    index["terms"][term]["df"] += 1
                    index["terms"][term]["postings"][document_id] = tf

                index["document_count"] += 1

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.output_path.open("w", encoding="utf-8") as file:
            json.dump(index, file, ensure_ascii=False)

        print(f"[DONE] {index['document_count']} documents, {len(index['terms'])} terms -> {self.output_path}")


if __name__ == "__main__":
    config_path = Path(__file__).with_name("config.json")
    indexer = Indexer(config_path)
    indexer.build()
