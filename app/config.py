DOMAIN = "www.rottentomatoes.com"
BASE_URL = f"https://{DOMAIN}"

USER_AGENT = "MartinHnatko-VINF-Crawler-StudentProject"

TIMEOUT = 10
SLEEP = 2

SEEDS = [
    "https://www.rottentomatoes.com/",
    "https://www.rottentomatoes.com/browse/movies_in_theaters/",
    "https://www.rottentomatoes.com/browse/movies_at_home/",
    "https://www.rottentomatoes.com/browse/movies_coming_soon/"
]

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

DATA_DIR = "data/raw"