"""
Uybozor single-listing parser.

This is a small test scraper for Uybozor detail pages. It normalizes listings
into the same schema used by the OLX scraper and writes a separate sample CSV.

Run:
    python3 scraper/uybozor.py
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from bs4 import FeatureNotFound

_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))

from config import COLUMNS, HEADERS


BASE_URL = "https://uybozortv.uz"
DEFAULT_URL = "https://uybozortv.uz/property-info/duplex-kvartira-mp19j3en"
DEFAULT_LISTING_PAGE = "https://uybozortv.uz/search"
DEFAULT_OUTPUT = "data/raw/uybozor_apartments_sample.csv"
_PROJECT_DIR = _SCRIPT_DIR.parent


def _build_soup(html: str) -> BeautifulSoup:
    try:
        return BeautifulSoup(html, "html.parser")
    except FeatureNotFound:
        return BeautifulSoup(html, "lxml")


class UybozorScraper:
    _FIELD_MAP = {
        "Maydoni": "total_area_m2",
        "Qavatlar soni": "total_floors",
        "Kvartira qavati": "floor",
        "Xonalar soni": "rooms",
        "Ta'mir": "renovation",
        "Nimadan qurilgan": "building_type",
    }

    _REGION_MAP = {
        "toshkent viloyati": "Tashkent Region",
        "toshkent shaxri": "Tashkent City",
        "toshkent shahri": "Tashkent City",
        "xorazm viloyati": "Khorezm Region",
    }

    _DISTRICT_MAP = {
        "toshkent tumani": "Tashkent District",
        "uchtepa tumani": "Uchtepa District",
        "mirzo ulug'bek tumani": "Mirzo-Ulugbek District",
        "mirzo-ulug'bek tumani": "Mirzo-Ulugbek District",
        "yashnobod tumani": "Yashnabad District",
        "shayxontohur tumani": "Shaykhantakhur District",
        "sergeli tumani": "Sergeli District",
        "yunusobod tumani": "Yunusabad District",
        "urganch tumani": "Urganch District",
    }

    _AMENITY_MAP = {
        "oshxona": "Kitchen",
        "muzlatgich": "Refrigerator",
        "kir yuvish mashinasi": "Washing Machine",
        "gaz plita": "Gas Stove",
        "konditsioner": "Air Conditioning",
        "wi-fi": "Internet",
        "wifi": "Internet",
    }

    _NEARBY_MAP = {
        "maktab": "School",
        "bog'cha": "Kindergarten",
        "do'kon": "Shops",
        "bekatlar": "Bus Stop",
        "bekat": "Bus Stop",
        "bozor": "Market",
        "masjid": "Mosque",
        "shifoxona": "Hospital",
        "choyxona": "Cafe",
    }

    _RENOVATION_MAP = {
        "a'lo": "excellent",
        "alo": "excellent",
        "yaxshi": "good",
        "o'rtacha": "average condition",
        "ta'mirtalab": "needs renovation",
    }

    _BUILDING_TYPE_MAP = {
        "g'isht": "brick",
        "gisht": "brick",
        "panel": "panel",
        "monolit": "monolith",
        "blok": "block",
    }

    _MONTHS = {
        "yanvar": 1,
        "fevral": 2,
        "mart": 3,
        "aprel": 4,
        "may": 5,
        "iyun": 6,
        "iyul": 7,
        "avgust": 8,
        "sentabr": 9,
        "sentyabr": 9,
        "oktabr": 10,
        "noyabr": 11,
        "dekabr": 12,
    }

    def __init__(self):
        self.session = requests.Session()
        headers = HEADERS.copy()
        headers.pop("Accept-Encoding", None)
        headers["Referer"] = "https://uybozortv.uz/"
        self.session.headers.update(headers)

    def _get(self, url: str) -> BeautifulSoup:
        resp = self.session.get(url, timeout=30)
        resp.raise_for_status()
        return _build_soup(resp.text)

    def get_listing_urls(self, page_url: str = DEFAULT_LISTING_PAGE) -> list[str]:
        soup = self._get(page_url)
        links = []
        seen = set()

        for a in soup.find_all("a", href=True):
            href = a["href"].split("?")[0]
            if "/property-info/" not in href:
                continue
            full_url = urljoin(BASE_URL, href)
            if full_url in seen:
                continue
            seen.add(full_url)
            links.append(full_url)

        return links

    def scrape(
        self,
        limit: int = 5,
        page_url: str = DEFAULT_LISTING_PAGE,
        apartments_only: bool = True,
        max_candidates: int = 40,
    ) -> list[dict]:
        rows = []
        for url in self.get_listing_urls(page_url)[:max_candidates]:
            if len(rows) >= limit:
                break

            try:
                row = self.parse_detail(url)
            except requests.RequestException as exc:
                print(f"Skipping {url}: {exc}", file=sys.stderr)
                continue

            if apartments_only and not self._looks_like_apartment(row):
                print(f"Skipping non-apartment listing: {url}", file=sys.stderr)
                time.sleep(1)
                continue

            rows.append(row)
            time.sleep(1)

        return rows

    @staticmethod
    def _looks_like_apartment(row: dict) -> bool:
        return row.get("total_area_m2") is not None and row.get("floor") is not None

    @staticmethod
    def save_csv(rows: list[dict], output: str | Path):
        output_path = Path(output)
        if not output_path.is_absolute():
            output_path = _PROJECT_DIR / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        df = pd.DataFrame(rows, columns=COLUMNS)
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        return output_path

    @staticmethod
    def _extract_id(url: str) -> str:
        return urlparse(url).path.rstrip("/").split("/")[-1]

    def parse_detail(self, url: str = DEFAULT_URL) -> dict:
        soup = self._get(url)

        listing = {col: None for col in COLUMNS}
        listing["listing_id"] = self._extract_id(url)
        listing["source"] = "uybozor"
        listing["date_scraped"] = datetime.now().strftime("%Y-%m-%d")
        listing["url"] = url

        json_ld = self._extract_real_estate_json_ld(soup)
        if json_ld:
            self._parse_json_ld(json_ld, listing)

        facts = self._extract_label_values(soup)
        self._parse_facts(facts, listing)

        if listing["amenities"] is None:
            listing["amenities"] = self._extract_list_after_heading(soup, "Sharoitlari", self._AMENITY_MAP)

        if listing["nearby"] is None:
            listing["nearby"] = self._extract_list_after_heading(soup, "Yaqin manzillar", self._NEARBY_MAP)

        if listing["price"] is None:
            listing["price"], listing["currency"] = self._extract_price(soup)

        if listing["description"] is None:
            meta = soup.find("meta", attrs={"name": "description"})
            listing["description"] = meta.get("content") if meta else None

        return listing

    @staticmethod
    def _extract_real_estate_json_ld(soup: BeautifulSoup) -> dict | None:
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or script.get_text() or "{}")
            except json.JSONDecodeError:
                continue
            if data.get("@type") == "RealEstateListing":
                return data
        return None

    def _parse_json_ld(self, data: dict, listing: dict):
        listing["description"] = data.get("description") or listing["description"]

        date_posted = data.get("datePosted")
        if date_posted:
            listing["published_date"] = self._format_iso_date(date_posted)

        offer = data.get("offers") or {}
        if offer:
            listing["price"] = self._to_number(offer.get("price"))
            listing["currency"] = offer.get("priceCurrency") or listing["currency"]

        address = data.get("address") or {}
        listing["region"] = self._normalize_region(address.get("addressRegion")) or listing["region"]
        listing["district"] = self._normalize_district(address.get("addressLocality")) or listing["district"]

    def _extract_label_values(self, soup: BeautifulSoup) -> dict:
        facts = {}
        for row in soup.find_all("div", class_=re.compile(r"\bflex\b")):
            label_el = row.find("p")
            value_el = row.find("span")
            if not label_el or not value_el:
                continue

            label = label_el.get_text(" ", strip=True).replace(":", "").strip()
            label = re.sub(r"\s*\(m²\)\s*", "", label).strip()
            value = value_el.get_text(" ", strip=True)
            if label and value:
                facts[label] = value
        return facts

    def _parse_facts(self, facts: dict, listing: dict):
        for label, field in self._FIELD_MAP.items():
            if listing.get(field) is not None or label not in facts:
                continue
            listing[field] = self._clean_value(field, facts[label])

    @classmethod
    def _extract_list_after_heading(cls, soup: BeautifulSoup, heading: str, value_map: dict) -> str | None:
        heading_node = soup.find(string=re.compile(r"^\s*" + re.escape(heading) + r"\s*$"))
        if not heading_node:
            return None

        container = heading_node.parent
        for _ in range(4):
            if not container:
                return None
            text = container.get_text(" ", strip=True)
            if heading in text and len(text) > len(heading):
                raw = text.replace(heading, "", 1)
                return cls._translate_csv_list(raw, value_map)
            container = container.parent
        return None

    @staticmethod
    def _translate_csv_list(raw: str, value_map: dict) -> str | None:
        items = [item.strip(" ,") for item in raw.split(",")]
        translated = []
        for item in items:
            if not item:
                continue
            low = item.lower()
            value = next((eng for key, eng in value_map.items() if key in low), item)
            if value not in translated:
                translated.append(value)
        return ", ".join(translated) if translated else None

    def _extract_price(self, soup: BeautifulSoup) -> tuple[float | int | None, str | None]:
        pattern = re.compile(r"[\d\s]+(?:sh\.b|so'm|сум|USD|UZS)", re.IGNORECASE)
        for el in soup.find_all(["h1", "h2", "h3", "p", "span", "div"]):
            text = el.get_text(" ", strip=True)
            if len(text) < 80 and pattern.search(text):
                currency = "UZS" if "so'm" in text.lower() or "сум" in text.lower() else "USD"
                return self._to_number(text), currency
        return None, None

    @classmethod
    def _clean_value(cls, field: str, raw: str):
        raw = raw.strip()
        if field in ("rooms", "floor", "total_floors"):
            m = re.search(r"\d+", raw)
            return int(m.group()) if m else None
        if field == "total_area_m2":
            return cls._to_number(raw)
        if field == "renovation":
            return cls._RENOVATION_MAP.get(raw.lower(), raw)
        if field == "building_type":
            return cls._BUILDING_TYPE_MAP.get(raw.lower(), raw)
        return raw

    @staticmethod
    def _to_number(value) -> float | int | None:
        if value is None:
            return None
        match = re.search(r"\d+(?:[\s.,]\d+)*", str(value))
        if not match:
            return None
        number = match.group(0).replace(" ", "").replace(",", ".")
        try:
            parsed = float(number)
        except ValueError:
            return None
        return int(parsed) if parsed.is_integer() else parsed

    @classmethod
    def _format_iso_date(cls, value: str) -> str | None:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.strftime("%d/%m/%Y")
        except ValueError:
            return cls._format_visible_date(value)

    @classmethod
    def _format_visible_date(cls, value: str) -> str | None:
        match = re.search(r"(\d{1,2})\s+([A-Za-z']+)\s+(\d{4})", value)
        if not match:
            return None
        day = int(match.group(1))
        month = cls._MONTHS.get(match.group(2).lower())
        year = int(match.group(3))
        if not month:
            return None
        return f"{day:02d}/{month:02d}/{year}"

    @classmethod
    def _normalize_region(cls, value: str | None) -> str | None:
        if not value:
            return None
        cleaned = re.sub(r"\s+", " ", value).strip()
        return cls._REGION_MAP.get(cleaned.lower(), cleaned)

    @classmethod
    def _normalize_district(cls, value: str | None) -> str | None:
        if not value:
            return None
        cleaned = re.sub(r"\s+", " ", value).strip()
        return cls._DISTRICT_MAP.get(cleaned.lower(), cleaned)


def main():
    parser = argparse.ArgumentParser(description="Scrape a small Uybozor sample CSV")
    parser.add_argument("--limit", type=int, default=5, help="Number of listings to write (default: 5)")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help=f"CSV path (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--page-url", default=DEFAULT_LISTING_PAGE, help="Uybozor search/listing page URL")
    parser.add_argument("--url", default=None, help="Parse one detail URL instead of collecting from search")
    parser.add_argument(
        "--all-property-types",
        action="store_true",
        help="Do not filter for apartment-like listings.",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=40,
        help="Maximum search links to inspect while looking for rows (default: 40)",
    )
    args = parser.parse_args()

    scraper = UybozorScraper()
    rows = (
        [scraper.parse_detail(args.url or DEFAULT_URL)]
        if args.url
        else scraper.scrape(
            limit=args.limit,
            page_url=args.page_url,
            apartments_only=not args.all_property_types,
            max_candidates=args.max_candidates,
        )
    )

    output_path = scraper.save_csv(rows, args.output)
    print(f"Saved {len(rows)} row(s) -> {output_path}")
    print(pd.DataFrame(rows, columns=COLUMNS).to_string(index=False))


if __name__ == "__main__":
    main()
