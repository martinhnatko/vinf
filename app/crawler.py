import json #load config file
import re #regex for extracting links
import time #sleep between requests

from collections import deque #fifo frontier
from html import unescape #unescape html entities (&amp; -> &)
from pathlib import Path #save html files
from urllib.parse import urljoin, urlparse, urlunparse, urldefrag #url parsing and normalization
from urllib.request import Request, urlopen #http requests
from urllib.robotparser import RobotFileParser #robots.txt parser

class Crawler:

    #value of href attribute in double or single quotes
    HREF_RE = re.compile(
        r'''href\s*=\s*["']([^"']+)["']''',
        re.IGNORECASE
    )

    #main movie page, e.g. /m/inception
    MOVIE_RE = re.compile(
        r"^/m/[A-Za-z0-9_-]+/?$"
    )

    def __init__(self, config_path):
        #load cfg from json
        with open(config_path, encoding="utf-8") as file:
            config = json.load(file)

        self.domain = config["domain"]
        self.user_agent = config["user_agent"]
        self.timeout = config["timeout"]
        self.sleep = config["sleep"]
        self.max_attempts = config["max_attempts"]
        self.data_dir = Path(config["data_dir"])
        #user agent + other headers from config
        self.headers = {
            "User-Agent": self.user_agent,
            **config["headers"]
        }

        self.frontier = deque(config["seeds"]) #urls to process
        self.queued = set(config["seeds"]) #urls that were already queued
        self.seen = set() #urls that were already processed
        self.attempts = {} #number of failed attempts per url

        #download robots.txt
        self.robots = RobotFileParser()
        self.robots.set_url(f"https://{self.domain}/robots.txt")
        self.robots.read()

    def normalize_url(self, url):
        #unify url form so the same page is not downloaded twice
        url, _ = urldefrag(url) #remove #fragment
        parsed = urlparse(url)

        return urlunparse((
            "https", #always https
            parsed.netloc.lower(), #lowercase domain
            parsed.path.rstrip("/"), #no trailing slash
            "", #no params
            "", #no query
            "" #no fragment
        ))

    def is_allowed_url(self, url):
        #only movie pages on our domain are allowed
        parsed = urlparse(url)

        if parsed.netloc != self.domain:
            return False

        return bool(self.MOVIE_RE.match(parsed.path))

    def extract_links(self, html, current_url):
        #return all movie links from the page
        links = []

        for href in self.HREF_RE.findall(html):
            href = unescape(href)

            url = urljoin(current_url, href) #relative url -> absolute
            url = self.normalize_url(url)

            if self.is_allowed_url(url):
                links.append(url)

        return links

    def download(self, url):
        #download page
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

            #invalid bytes are replaced so the program does not crash
            return response.read().decode(
                "utf-8",
                errors="replace"
            )

    def save_html(self, url, html):
        #save page as <movie_name>.html
        directory = self.data_dir
        directory.mkdir(
            parents=True,
            exist_ok=True
        )

        movie_name = urlparse(url).path.split("/")[-1] #last part of the path, e.g. inception

        file_path = directory / f"{movie_name}.html"

        file_path.write_text(
            html,
            encoding="utf-8"
        )

    def add_links(self, links):
        #add only new urls to the frontier
        for link in links:
            if link in self.seen:
                continue

            if link in self.queued:
                continue

            self.frontier.append(link)
            self.queued.add(link)

    def retry(self, url):
        #put failed url back to the end of the frontier
        self.attempts[url] = self.attempts.get(url, 0) + 1

        if self.attempts[url] >= self.max_attempts:
            print("[FAILED]", url)
            return

        self.seen.discard(url) #allow processing the url again
        self.frontier.append(url)
        print(
            f"[RETRY] {url} "
            f"attempt={self.attempts[url] + 1}/{self.max_attempts}"
        )

    def crawl(self):
        #bfs crawl while the frontier is not empty
        while self.frontier:

            url = self.frontier.popleft()
            url = self.normalize_url(url) #seeds in config are not normalized

            if url in self.seen:
                continue

            self.seen.add(url)

            #check if robots.txt allows fetching
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

                #save only movie pages, not seeds
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

            except Exception as error:
                print("[ERROR]", url, error)
                self.retry(url)

            finally:
                time.sleep(self.sleep) #do not overload the server