from pathlib import Path

from crawler import Crawler

CONFIG_PATH = Path(__file__).with_name("config.json")


def main():
    crawler = Crawler(CONFIG_PATH)
    crawler.crawl()


if __name__ == "__main__":
    main()
