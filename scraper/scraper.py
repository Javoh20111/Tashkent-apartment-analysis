"""
OLX.uz apartment scraper.

Pipeline:
  1. Loop through category pages (?page=1 … ?page=N)
  2. Collect individual listing URLs from each page
  3. Fetch each detail page and parse characteristics
  4. Skip already-seen listing IDs (deduplication)
  5. Append new rows to CSV — never overwrite existing data

Run manually:
    cd scraper/
    python scraper.py

Cron (daily at 08:00) — see ../run_scraper.sh
"""

import json
import logging
import re
import sys
import time
import random
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

# Resolve paths relative to this file so the script works regardless of CWD
_SCRIPT_DIR = Path(__file__).resolve().parent   # .../scraper/
_PROJECT_DIR = _SCRIPT_DIR.parent               # .../Tashkent apartment analysis/

sys.path.insert(0, str(_SCRIPT_DIR))
from config import (
    BASE_URL, COLUMNS, DELAY_MAX, DELAY_MIN, FIELD_MAP,
    HEADERS, MAX_PAGES, MAX_RETRIES, BACKOFF_BASE,
    OUTPUT_DIR, LOG_DIR, CSV_FILENAME,
)

# Make OUTPUT_DIR and LOG_DIR absolute so they always land inside the project
_OUTPUT_DIR = (_PROJECT_DIR / OUTPUT_DIR).resolve()
_LOG_DIR    = (_PROJECT_DIR / LOG_DIR).resolve()

# ---------------------------------------------------------------------------
# Logging — writes to logs/scraper_YYYYMMDD.log AND to the terminal
# ---------------------------------------------------------------------------
_LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file = _LOG_DIR / f"scraper_{datetime.now():%Y%m%d}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------
class OLXScraper:

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.csv_path = _OUTPUT_DIR / CSV_FILENAME
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.seen_ids: set[str] = self._load_existing_ids()
        log.info(f"Loaded {len(self.seen_ids)} already-scraped IDs from {self.csv_path}")

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------
    def _load_existing_ids(self) -> set[str]:
        if self.csv_path.exists():
            try:
                df = pd.read_csv(self.csv_path, usecols=["listing_id"], dtype=str)
                return set(df["listing_id"].dropna())
            except Exception as e:
                log.warning(f"Could not read existing CSV: {e}")
        return set()

    # ------------------------------------------------------------------
    # HTTP with rate-limit handling and exponential backoff
    # ------------------------------------------------------------------
    def _get(self, url: str) -> BeautifulSoup | None:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self.session.get(url, timeout=30)

                if resp.status_code == 200:
                    return BeautifulSoup(resp.text, "lxml")

                if resp.status_code == 429:
                    # Respect Retry-After if present, otherwise use exponential backoff
                    wait = int(resp.headers.get("Retry-After", BACKOFF_BASE ** attempt))
                    log.warning(f"429 rate-limited on {url}. Sleeping {wait}s …")
                    time.sleep(wait)
                    continue

                if resp.status_code in (403, 404):
                    log.warning(f"HTTP {resp.status_code} — skipping {url}")
                    return None

                log.warning(f"HTTP {resp.status_code} on attempt {attempt}/{MAX_RETRIES}: {url}")
                time.sleep(BACKOFF_BASE ** attempt)

            except requests.RequestException as exc:
                log.error(f"Request error (attempt {attempt}/{MAX_RETRIES}): {exc}")
                time.sleep(BACKOFF_BASE ** attempt)

        log.error(f"Giving up after {MAX_RETRIES} attempts: {url}")
        return None

    def _delay(self):
        """Random human-like pause between requests."""
        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    # ------------------------------------------------------------------
    # Listing-page: collect detail URLs
    # ------------------------------------------------------------------
    def _get_listing_urls(self, page: int) -> list[str]:
        url = f"{BASE_URL}?page={page}"
        log.info(f"Fetching listing page {page}: {url}")
        soup = self._get(url)
        if not soup:
            return []

        links: list[str] = []
        seen_on_page: set[str] = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/d/obyavlenie/" not in href:
                continue
            # Normalise to absolute URL, strip query params
            full = ("https://www.olx.uz" + href) if href.startswith("/") else href
            full = full.split("?")[0]
            if full not in seen_on_page:
                seen_on_page.add(full)
                links.append(full)

        log.info(f"  → {len(links)} unique listing URLs on page {page}")
        return links

    # ------------------------------------------------------------------
    # Detail page: parse all fields
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_id(url: str) -> str:
        m = re.search(r"-ID([A-Za-z0-9]+)\.html", url)
        return m.group(1) if m else url

    def _parse_detail(self, url: str) -> dict | None:
        soup = self._get(url)
        if not soup:
            return None

        listing: dict = {col: None for col in COLUMNS}
        listing["url"] = url
        listing["listing_id"] = self._extract_id(url)
        listing["date_scraped"] = datetime.now().strftime("%Y-%m-%d")

        # --- 1. Try __NEXT_DATA__ (Next.js JSON embedded in page) --------
        next_script = soup.find("script", id="__NEXT_DATA__")
        if next_script:
            try:
                data = json.loads(next_script.string or "")
                self._parse_next_data(data, listing)
                # Fill remaining fields from HTML if JSON was partial
            except (json.JSONDecodeError, AttributeError):
                pass

        # --- 2. Price -----------------------------------------------------
        if listing["price"] is None:
            listing["price"], listing["currency"] = self._extract_price(soup)

        # --- 3. Characteristics (rooms, area, floor …) -------------------
        self._extract_characteristics(soup, listing)

        # --- 4. District --------------------------------------------------
        if listing["district"] is None:
            listing["district"] = self._extract_district(soup)

        # --- 5. Description -----------------------------------------------
        if listing["description"] is None:
            listing["description"] = self._extract_description(soup)

        return listing

    # ------------------------------------------------------------------
    # Field extractors
    # ------------------------------------------------------------------
    def _extract_characteristics(self, soup: BeautifulSoup, listing: dict):
        """
        OLX renders characteristics as adjacent label-value elements.
        We search for each Russian label string and read the value from
        the same element (if "Label: value") or from the next sibling.
        """
        for ru_label, field in FIELD_MAP.items():
            if listing.get(field) is not None:
                continue  # already filled from __NEXT_DATA__

            # Find the text node that exactly matches the label
            node = soup.find(string=re.compile(r"^\s*" + re.escape(ru_label) + r":?\s*$"))
            if not node:
                continue

            raw_text = node.strip()
            if ":" in raw_text and len(raw_text) > len(ru_label) + 1:
                # "Label: value" in one string
                value = raw_text.split(":", 1)[1].strip()
            else:
                # Label and value are in sibling elements
                parent = node.parent
                sibling = parent.find_next_sibling() if parent else None
                if not sibling:
                    # Try grandparent's next sibling
                    if parent and parent.parent:
                        sibling = parent.parent.find_next_sibling()
                if not sibling:
                    continue
                value = sibling.get_text(strip=True)

            if value:
                listing[field] = self._clean_value(field, value)

    def _extract_price(self, soup: BeautifulSoup) -> tuple[float | None, str]:
        price_pattern = re.compile(r"[\d\s]+(?:у\.е\.|сум|UZS|USD|\$)")
        for el in soup.find_all(["strong", "span", "div", "p"]):
            text = el.get_text(strip=True)
            if price_pattern.search(text) and len(text) < 40:
                return self._parse_price_text(text)
        return None, "USD"

    @staticmethod
    def _parse_price_text(text: str) -> tuple[float | None, str]:
        currency = "USD"
        if "сум" in text.lower() or "uzs" in text.lower():
            currency = "UZS"
        elif "у.е." in text or "$" in text or "usd" in text.lower():
            currency = "USD"
        elif "rub" in text.lower() or "руб" in text.lower():
            currency = "RUB"

        num_str = re.sub(r"[^\d.]", "", text)
        try:
            return float(num_str), currency
        except ValueError:
            return None, currency

    @staticmethod
    def _extract_district(soup: BeautifulSoup) -> str | None:
        # Breadcrumb is the most reliable source for the district
        for nav in soup.find_all(["nav", "ol", "ul"]):
            crumbs = nav.find_all("a")
            # Typical breadcrumb: Home > Real estate > Apartments > Tashkent > District
            if len(crumbs) >= 3:
                last_text = crumbs[-1].get_text(strip=True)
                # Filter out generic category names
                if last_text and "квартир" not in last_text.lower():
                    return last_text
        # Fallback: look for a location/address element
        for el in soup.find_all(["p", "span", "div"]):
            text = el.get_text(strip=True)
            if "район" in text.lower() and len(text) < 60:
                return text
        return None

    @staticmethod
    def _extract_description(soup: BeautifulSoup) -> str | None:
        # OLX puts description in a <div> that often has "description" in its class
        for el in soup.find_all(["div", "section"]):
            cls = " ".join(el.get("class", []))
            if "description" in cls.lower():
                text = el.get_text(separator=" ", strip=True)
                if len(text) > 20:
                    return text[:1000]
        return None

    @staticmethod
    def _clean_value(field: str, raw: str) -> int | float | str | None:
        raw = raw.strip()
        if field in ("rooms", "floor", "total_floors"):
            m = re.search(r"\d+", raw)
            return int(m.group()) if m else None
        if field in ("living_area_m2", "total_area_m2"):
            m = re.search(r"[\d,]+", raw)
            return float(m.group().replace(",", ".")) if m else None
        if field == "furnished":
            return 1 if raw.lower() in ("да", "yes", "есть", "мебелирована") else 0
        if field == "commission":
            return 0 if raw.lower() in ("нет", "no", "без комиссии", "0") else 1
        return raw

    # ------------------------------------------------------------------
    # __NEXT_DATA__ JSON parser (used when OLX embeds data in the page)
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_next_data(data: dict, listing: dict):
        try:
            ad = data["props"]["pageProps"]["ad"]
        except (KeyError, TypeError):
            return

        listing["listing_id"] = str(ad.get("id", listing["listing_id"]))

        price_block = ad.get("price", {})
        if price_block:
            listing["price"] = price_block.get("value")
            listing["currency"] = price_block.get("currency", "USD")

        listing["description"] = (ad.get("description") or "")[:1000]

        # Params are an array like [{"key": "rooms", "value": {"label": "2"}}]
        for param in ad.get("params", []):
            key = param.get("key", "")
            label = (param.get("value") or {}).get("label", "")
            if key in FIELD_MAP:
                listing[FIELD_MAP[key]] = label

        # Location
        location = ad.get("location", {})
        city_name = (location.get("city") or {}).get("name", "")
        district_name = (location.get("district") or {}).get("name", "")
        listing["district"] = district_name or city_name or None

    # ------------------------------------------------------------------
    # Persistence — append-only
    # ------------------------------------------------------------------
    def _save(self, rows: list[dict]):
        if not rows:
            return
        df = pd.DataFrame(rows, columns=COLUMNS)
        write_header = not self.csv_path.exists()
        df.to_csv(self.csv_path, mode="a", header=write_header, index=False, encoding="utf-8")
        log.info(f"Saved {len(rows)} new rows → {self.csv_path}")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run(self, max_pages: int = MAX_PAGES):
        log.info(f"===== Scrape started — up to {max_pages} pages =====")
        total_new = 0

        for page in range(1, max_pages + 1):
            urls = self._get_listing_urls(page)
            if not urls:
                log.info(f"No listings found on page {page} — stopping pagination.")
                break

            self._delay()

            batch: list[dict] = []
            for url in urls:
                lid = self._extract_id(url)
                if lid in self.seen_ids:
                    log.info(f"  Duplicate — skipping {lid}")
                    continue

                detail = self._parse_detail(url)
                if detail:
                    batch.append(detail)
                    self.seen_ids.add(lid)
                    log.info(f"  Scraped {lid}")

                self._delay()   # polite pause between detail requests

            self._save(batch)
            total_new += len(batch)
            log.info(f"Page {page} complete — new: {len(batch)}, total new: {total_new}")
            self._delay()       # extra pause between listing pages

        log.info(f"===== Scrape finished — {total_new} new listings =====")
        return total_new


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    OLXScraper().run()
