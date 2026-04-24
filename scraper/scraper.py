"""
OLX.uz apartment scraper.

Pipeline:
  1. Loop through category pages (?page=1 … ?page=N)
  2. Collect individual listing URLs from each page
  3. Fetch each detail page and parse characteristics
  4. Skip already-seen listing IDs (deduplication)
  5. Append new rows to CSV — never overwrite existing data

Run manually (all pages):
    python scraper.py

Test run — 1 page only:
    python scraper.py --pages 1

Cron (daily at 08:00) — see ../run_scraper.sh
"""

import argparse
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
from bs4 import FeatureNotFound

# Resolve paths relative to this file so the script works regardless of CWD
_SCRIPT_DIR  = Path(__file__).resolve().parent   # .../scraper/
_PROJECT_DIR = _SCRIPT_DIR.parent                # .../Tashkent apartment analysis/

sys.path.insert(0, str(_SCRIPT_DIR))
from config import (
    BASE_URL, BREADCRUMB_SKIP, COLUMNS, DELAY_MAX, DELAY_MIN, FIELD_MAP,
    HEADERS, MAX_PAGES, MAX_RETRIES, BACKOFF_BASE,
    OUTPUT_DIR, LOG_DIR, CSV_FILENAME, UZBEKISTAN_REGIONS, VALUE_TRANSLATIONS,
)

# Absolute paths — always land inside the project no matter where you run from
_OUTPUT_DIR = (_PROJECT_DIR / OUTPUT_DIR).resolve()
_LOG_DIR    = (_PROJECT_DIR / LOG_DIR).resolve()

# ---------------------------------------------------------------------------
# Logging
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


def _build_soup(html: str) -> BeautifulSoup:
    try:
        return BeautifulSoup(html, "lxml")
    except FeatureNotFound:
        return BeautifulSoup(html, "html.parser")


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
    # HTTP — rate-limit handling + exponential backoff
    # ------------------------------------------------------------------
    def _get(self, url: str) -> BeautifulSoup | None:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self.session.get(url, timeout=30)

                if resp.status_code == 200:
                    return _build_soup(resp.text)

                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", BACKOFF_BASE ** attempt))
                    log.warning(f"429 rate-limited. Sleeping {wait}s …")
                    time.sleep(wait)
                    continue

                if resp.status_code in (403, 404):
                    log.warning(f"HTTP {resp.status_code} — skipping {url}")
                    return None

                log.warning(f"HTTP {resp.status_code} attempt {attempt}/{MAX_RETRIES}: {url}")
                time.sleep(BACKOFF_BASE ** attempt)

            except requests.RequestException as exc:
                log.error(f"Request error attempt {attempt}/{MAX_RETRIES}: {exc}")
                time.sleep(BACKOFF_BASE ** attempt)

        log.error(f"Giving up after {MAX_RETRIES} attempts: {url}")
        return None

    def _delay(self):
        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    # ------------------------------------------------------------------
    # Listing page — collect detail URLs
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
            full = ("https://www.olx.uz" + href) if href.startswith("/") else href
            full = full.split("?")[0]
            if full not in seen_on_page:
                seen_on_page.add(full)
                links.append(full)

        log.info(f"  → {len(links)} unique listing URLs on page {page}")
        return links

    # ------------------------------------------------------------------
    # Detail page — parse all fields
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
        listing["url"]          = url
        listing["listing_id"]   = self._extract_id(url)
        listing["date_scraped"] = datetime.now().strftime("%Y-%m-%d")

        # 1. Try __NEXT_DATA__ JSON (Next.js sites embed data here)
        next_script = soup.find("script", id="__NEXT_DATA__")
        if next_script:
            try:
                data = json.loads(next_script.string or "")
                self._parse_next_data(data, listing)
            except (json.JSONDecodeError, AttributeError):
                pass

        # 2. Characteristics from HTML (fills any gap left by __NEXT_DATA__)
        self._extract_characteristics(soup, listing)

        # 3. Price
        if listing["price"] is None:
            listing["price"], listing["currency"] = self._extract_price(soup)

        # 4. Region + district from breadcrumb
        if listing["region"] is None or listing["district"] is None:
            self._extract_location(soup, listing)

        # 5. Description
        if listing["description"] is None:
            listing["description"] = self._extract_description(soup)

        return listing

    # ------------------------------------------------------------------
    # Characteristics — Russian label → column value
    # ------------------------------------------------------------------
    def _extract_characteristics(self, soup: BeautifulSoup, listing: dict):
        """
        OLX.uz renders characteristics as label : value pairs, either in
        the same text node ("Количество комнат: 2") or as adjacent siblings
        (label element followed by value element).
        """
        for ru_label, field in FIELD_MAP.items():
            if listing.get(field) is not None:
                continue

            # Match text node that is exactly the label (with optional colon)
            pattern = re.compile(r"^\s*" + re.escape(ru_label) + r":?\s*$")
            node = soup.find(string=pattern)

            if not node:
                # Also try "Label: value" in a single node
                combined = soup.find(
                    string=re.compile(r"^\s*" + re.escape(ru_label) + r":\s*.+")
                )
                if combined:
                    value = combined.strip().split(":", 1)[1].strip()
                    listing[field] = self._clean_value(field, value)
                continue

            raw_text = node.strip()
            if ":" in raw_text and len(raw_text) > len(ru_label) + 1:
                value = raw_text.split(":", 1)[1].strip()
            else:
                # Value is in a sibling element
                parent  = node.parent
                sibling = parent.find_next_sibling() if parent else None
                if not sibling and parent and parent.parent:
                    sibling = parent.parent.find_next_sibling()
                if not sibling:
                    continue
                value = sibling.get_text(strip=True)

            if value:
                listing[field] = self._clean_value(field, value)

    # ------------------------------------------------------------------
    # Location — region + district from breadcrumb
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_location_name(value: str | None) -> str | None:
        if not value:
            return None

        cleaned = re.sub(r"\s+", " ", value).strip(" ,")
        cleaned = re.sub(
            r"^(?:Продажа|Аренда(?:\s+долгосрочная)?|Посуточно)\s*-\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        if not cleaned:
            return None

        normalized = cleaned.lower().replace("’", "'").replace("`", "'")
        if normalized in BREADCRUMB_SKIP:
            return None

        region_aliases = {
            "toshkent": "Tashkent City",
            "tashkent": "Tashkent City",
            "город ташкент": "Tashkent City",
            "ташкент": "Tashkent City",
            "ташкентская область": "Tashkent Region",
            "toshkent viloyati": "Tashkent Region",
            "andijon": "Andijan Region",
            "андижанская область": "Andijan Region",
            "buxoro": "Bukhara Region",
            "бухарская область": "Bukhara Region",
            "farg'ona": "Fergana Region",
            "fergana": "Fergana Region",
            "ферганская область": "Fergana Region",
            "jizzax": "Jizzakh Region",
            "джизакская область": "Jizzakh Region",
            "xorazm": "Khorezm Region",
            "хорезмская область": "Khorezm Region",
            "namangan": "Namangan Region",
            "наманганская область": "Namangan Region",
            "navoiy": "Navoiy Region",
            "навоийская область": "Navoiy Region",
            "навойская область": "Navoiy Region",
            "навойская область": "Navoiy Region",
            "qashqadaryo": "Kashkadarya Region",
            "кашкадарьинская область": "Kashkadarya Region",
            "samarqand": "Samarkand Region",
            "самаркандская область": "Samarkand Region",
            "sirdaryo": "Sirdaryo Region",
            "сырдарьинская область": "Sirdaryo Region",
            "surxondaryo": "Surxondaryo Region",
            "сурхандарьинская область": "Surxondaryo Region",
            "qoraqalpog'iston": "Republic of Karakalpakstan",
            "каракалпакстан": "Republic of Karakalpakstan",
        }
        return region_aliases.get(normalized, cleaned)

    @classmethod
    def _looks_like_region(cls, value: str | None) -> bool:
        normalized = cls._normalize_location_name(value)
        return bool(normalized and normalized.lower() in UZBEKISTAN_REGIONS)

    @classmethod
    def _extract_location(cls, soup: BeautifulSoup, listing: dict):
        """
        Breadcrumb structure on OLX.uz:
          Главная > Недвижимость > Квартиры > [Region] > [District]

        We skip category-level crumbs and take the last two meaningful ones.
        """
        for nav in soup.find_all(["nav", "ol", "ul"]):
            crumbs = [
                cls._normalize_location_name(a.get_text(strip=True))
                for a in nav.find_all("a")
            ]
            crumbs = [
                crumb for crumb in crumbs
                if crumb
            ]

            if not crumbs:
                continue

            region_index = next(
                (i for i, crumb in enumerate(crumbs) if cls._looks_like_region(crumb)),
                None,
            )
            if region_index is not None:
                listing["region"] = crumbs[region_index]
                if region_index + 1 < len(crumbs):
                    listing["district"] = crumbs[region_index + 1]
                return

            if len(crumbs) >= 2:
                listing["region"] = crumbs[-2]
                listing["district"] = crumbs[-1]
                return

        # Fallback — scan for "район" keyword in short text blocks
        for el in soup.find_all(["p", "span", "div"]):
            text = el.get_text(strip=True)
            if "район" in text.lower() and len(text) < 80:
                listing["district"] = text
                return

    # ------------------------------------------------------------------
    # Price
    # ------------------------------------------------------------------
    def _extract_price(self, soup: BeautifulSoup) -> tuple[float | None, str]:
        pattern = re.compile(r"[\d\s]+(?:у\.е\.|сум|UZS|USD|\$)")
        for el in soup.find_all(["strong", "span", "div", "p"]):
            text = el.get_text(strip=True)
            if pattern.search(text) and len(text) < 40:
                return self._parse_price_text(text)
        return None, "USD"

    @staticmethod
    def _parse_price_text(text: str) -> tuple[float | None, str]:
        if "сум" in text.lower() or "uzs" in text.lower():
            currency = "UZS"
        elif "rub" in text.lower() or "руб" in text.lower():
            currency = "RUB"
        else:
            currency = "USD"   # у.е. / $ / default

        num_str = re.sub(r"[^\d.]", "", text)
        try:
            return float(num_str), currency
        except ValueError:
            return None, currency

    # ------------------------------------------------------------------
    # Description
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_description(soup: BeautifulSoup) -> str | None:
        for el in soup.find_all(["div", "section"]):
            cls = " ".join(el.get("class", []))
            if "description" in cls.lower():
                text = el.get_text(separator=" ", strip=True)
                if len(text) > 20:
                    return text[:1000]
        return None

    # ------------------------------------------------------------------
    # Value cleaning / type coercion
    # ------------------------------------------------------------------
    @staticmethod
    def _clean_value(field: str, raw: str) -> int | float | str | None:
        raw = raw.strip()
        if field in ("rooms", "floor", "total_floors"):
            m = re.search(r"\d+", raw)
            return int(m.group()) if m else None
        if field in ("living_area_m2", "total_area_m2", "kitchen_area_m2"):
            m = re.search(r"[\d,]+", raw)
            return float(m.group().replace(",", ".")) if m else None
        if field == "furnished":
            return 1 if raw.lower() in ("да", "yes", "есть", "мебелирована") else 0
        if field == "commission":
            return 0 if raw.lower() in ("нет", "no", "без комиссии", "0") else 1
        if field == "build_year":
            return raw   # keep range string e.g. "1990 - 2000"
        translations = VALUE_TRANSLATIONS.get(field, {})
        return translations.get(raw.lower(), raw)

    # ------------------------------------------------------------------
    # __NEXT_DATA__ JSON parser
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
            listing["price"]    = price_block.get("value")
            listing["currency"] = price_block.get("currency", "USD")

        listing["description"] = (ad.get("description") or "")[:1000]

        for param in ad.get("params", []):
            key   = param.get("key", "")
            label = (param.get("value") or {}).get("label", "")
            if key in FIELD_MAP:
                field = FIELD_MAP[key]
                listing[field] = OLXScraper._clean_value(field, label)

        location      = ad.get("location", {})
        listing["region"] = OLXScraper._normalize_location_name(
            (location.get("region") or {}).get("name")
        )
        listing["district"] = OLXScraper._normalize_location_name(
            (location.get("district") or {}).get("name")
            or (location.get("city") or {}).get("name")
        )

    # ------------------------------------------------------------------
    # Persistence — append-only CSV
    # ------------------------------------------------------------------
    def _save(self, rows: list[dict]):
        if not rows:
            return
        df = pd.DataFrame(rows, columns=COLUMNS)
        write_header = not self.csv_path.exists()
        df.to_csv(self.csv_path, mode="a", header=write_header, index=False, encoding="utf-8-sig")
        log.info(f"Saved {len(rows)} new rows → {self.csv_path}")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run(self, max_pages: int = MAX_PAGES):
        log.info(f"===== Scrape started — up to {max_pages} page(s) =====")
        total_new = 0

        for page in range(1, max_pages + 1):
            urls = self._get_listing_urls(page)
            if not urls:
                log.info(f"No listings on page {page} — stopping.")
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

                self._delay()

            self._save(batch)
            total_new += len(batch)
            log.info(f"Page {page} done — new: {len(batch)}, total new: {total_new}")
            self._delay()

        log.info(f"===== Scrape finished — {total_new} new listings =====")
        return total_new


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OLX.uz apartment scraper")
    parser.add_argument(
        "--pages", type=int, default=MAX_PAGES,
        help=f"Number of listing pages to scrape (default: {MAX_PAGES}). Use 1 for a test run.",
    )
    args = parser.parse_args()
    OLXScraper().run(max_pages=args.pages)
