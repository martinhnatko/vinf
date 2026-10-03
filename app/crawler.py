import json #load config file
import re #regex for extracting links
import time #sleep between requests

from collections import deque #fifo frontier
from html import unescape #unescape html entities
from pathlib import Path #save html files
from urllib.parse import urljoin, urlparse, urlunparse, urldefrag #url parsing and normalization
from urllib.request import Request, urlopen #http requests
from urllib.robotparser import RobotFileParser #robots.txt parser

class Crawler:

    HREF_RE = re.compile(
        r'''href\s*=\s*["']([^"']+)["']''',
        re.IGNORECASE
    )

    MOVIE_RE = re.compile(
        r"^/m/[A-Za-z0-9_-]+/?$"
    )

    def __init__(self, config_path):
        with open(config_path, encoding="utf-8") as file:
            config = json.load(file)

        self.domain = config["domain"]
        self.user_agent = config["user_agent"]
        self.timeout = config["timeout"]
        self.sleep = config["sleep"]
        self.data_dir = Path(config["data_dir"])
        self.headers = {
            "User-Agent": self.user_agent,
            **config["headers"]
        }

        self.frontier = deque(config["seeds"])
        self.queued = set(config["seeds"])
        self.seen = set()

        self.robots = RobotFileParser()
        self.robots.set_url(f"https://{self.domain}/robots.txt")
        self.robots.read()

    def normalize_url(self, url):
        url, _ = urldefrag(url)
        parsed = urlparse(url)

        return urlunparse((
            "https",
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            "",
            "",
            ""
        ))

    def is_allowed_url(self, url):
        parsed = urlparse(url)

        if parsed.netloc != self.domain:
            return False

        return bool(self.MOVIE_RE.match(parsed.path))

    def extract_links(self, html, current_url):
        links = []

        for href in self.HREF_RE.findall(html):
            href = unescape(href)

            url = urljoin(current_url, href)
            url = self.normalize_url(url)

            if self.is_allowed_url(url):
                links.append(url)

        return links

    def download(self, url):
        request = Request(
            url,
            headers=self.headers
        )

        with urlopen(
            request,
            timeout=self.timeout
        ) as response:

            content_type = response.headers.get(
                "Content-Type",
                ""
            )

            if "text/html" not in content_type:
                return None

            return response.read().decode(
                "utf-8",
                errors="replace"
            )

    def save_html(self, url, html):
        directory = self.data_dir
        directory.mkdir(
            parents=True,
            exist_ok=True
        )

        slug = urlparse(url).path.split("/")[-1]

        file_path = directory / f"{slug}.html"

        file_path.write_text(
            html,
            encoding="utf-8"
        )

    def add_links(self, links):
        for link in links:
            if link in self.seen:
                continue

            if link in self.queued:
                continue

            self.frontier.append(link)
            self.queued.add(link)

    def crawl(self):
        while self.frontier:

            url = self.frontier.popleft()
            url = self.normalize_url(url)

            if url in self.seen:
                continue

            self.seen.add(url)

            if not self.robots.can_fetch(
                self.user_agent,
                url
            ):
                print("[ROBOTS]", url)
                continue

            try:
                print("[GET]", url)

                html = self.download(url)

                if html is None:
                    continue

                if self.is_allowed_url(url):
                    self.save_html(url, html)
                    print("[SAVE]", url)

                links = self.extract_links(
                    html,
                    url
                )

                self.add_links(links)

                print(
                    f"[STATE] "
                    f"seen={len(self.seen)} "
                    f"frontier={len(self.frontier)}"
                )

                time.sleep(self.sleep)

            except Exception as error:
                print("[ERROR]", url, error)