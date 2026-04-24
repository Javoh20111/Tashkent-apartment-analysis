BASE_URL = "https://www.olx.uz/nedvizhimost/kvartiry/"
MAX_PAGES = 25          # OLX caps category results at ~25 pages
DELAY_MIN = 1.5         # seconds — minimum human-like delay
DELAY_MAX = 4.0         # seconds — maximum human-like delay
MAX_RETRIES = 3         # attempts before giving up on a URL
BACKOFF_BASE = 2        # exponential backoff base in seconds

OUTPUT_DIR = "../data/raw"
LOG_DIR = "../logs"
CSV_FILENAME = "olx_apartments.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,uz;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Referer": "https://www.olx.uz/",
}

# Russian page label → CSV column name
FIELD_MAP = {
    "Количество комнат":  "rooms",
    "Жилая площадь":      "living_area_m2",
    "Общая площадь":      "total_area_m2",
    "Этаж":               "floor",
    "Количество этажей":  "total_floors",
    "Тип строения":       "building_type",
    "Санузел":            "bathroom",
    "Меблирована":        "furnished",
    "Ремонт":             "renovation",
    "Тип планировки":     "layout",
    "Комиссия":           "commission",
    "Вид недвижимости":   "housing_type",
    "Тип объявителя":     "seller_type",
    "Тип продавца":       "seller_type",   # alternate label
}

# Output columns — matches the user's data contract exactly
COLUMNS = [
    "listing_id",
    "seller_type",
    "housing_type",
    "district",
    "rooms",
    "living_area_m2",
    "total_area_m2",
    "floor",
    "total_floors",
    "building_type",
    "layout",
    "bathroom",
    "furnished",
    "renovation",
    "commission",
    "price",
    "currency",
    "description",
    "date_scraped",
    "url",             # extra — useful for deduplication and reference
]
