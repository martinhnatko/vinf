import re #regex for extracting links
import time #sleep between requests

from collections import deque #fifo frontier
from html import unescape #unescape html entities
from pathlib import Path #save html files
from urllib.parse import urljoin, urlparse, urlunparse, urldefrag #url parsing and normalization
from urllib.request import Request, urlopen #http requests
from urllib.robotparser import RobotFileParser #robots.txt parser

import config

class Crawler:

    HREF_RE = re.compile(
        r'''href\s*=\s*["']([^"']+)["']''',
        re.IGNORECASE
    )

    MOVIE_RE = re.compile(
        r"^/m/[A-Za-z0-9_-]+/?$"
    )

    def __init__(self):
        self.frontier = deque(config.SEEDS)
        self.queued = set(config.SEEDS)
        self.seen = set()

        self.robots = RobotFileParser()
        self.robots.set_url(config.BASE_URL + "/robots.txt")
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

        if parsed.netloc != config.DOMAIN:
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
            headers=config.HEADERS
        )

        with urlopen(
            request,
            timeout=config.TIMEOUT
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
        directory = Path(config.DATA_DIR)
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
                config.USER_AGENT,
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

                time.sleep(config.SLEEP)

            except Exception as error:
                print("[ERROR]", url, error)