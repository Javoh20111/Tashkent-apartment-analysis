BASE_URL = "https://www.olx.uz/nedvizhimost/kvartiry/"
MAX_PAGES = 1           # set to 25 when ready for full scrape
DELAY_MIN = 1.5         # seconds — minimum human-like delay
DELAY_MAX = 4.0         # seconds — maximum human-like delay
MAX_RETRIES = 3         # attempts before giving up on a URL
BACKOFF_BASE = 2        # exponential backoff base in seconds

OUTPUT_DIR = "data/raw"
LOG_DIR    = "logs"
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
# Labels taken directly from real OLX.uz listings
FIELD_MAP = {
    "Тип жилья":              "housing_type",    # Новостройки / Вторичное
    "Тип объявителя":         "seller_type",     # Частное лицо / Бизнес
    "Тип продавца":           "seller_type",     # alternate label
    "Количество комнат":      "rooms",
    "Жилая площадь":          "living_area_m2",
    "Общая площадь":          "total_area_m2",
    "Площадь кухни":          "kitchen_area_m2",
    "Этаж":                   "floor",
    "Этажность дома":         "total_floors",    # confirmed label from OLX.uz
    "Тип строения":           "building_type",   # Панельный / Кирпичный / Монолитный
    "Планировка":             "layout",          # Раздельная / Смежная
    "Год постройки/сдачи":    "build_year",
    "Санузел":                "bathroom",        # Раздельный / Совмещенный
    "Меблирована":            "furnished",       # Да / Нет → 1 / 0
    "Ремонт":                 "renovation",      # Евроремонт / Авторский проект / …
    "Комиссионные":           "commission",      # Да / Нет → 1 / 0
}

# Breadcrumb words to skip when extracting region / district
BREADCRUMB_SKIP = {
    "главная", "недвижимость", "квартиры", "квартира",
    "дома", "продажа", "аренда", "uzbekistan", "olx",
}

# Output columns — final schema
COLUMNS = [
    "listing_id",
    "seller_type",
    "housing_type",
    "region",           # which of the 13 Uzbekistan regions
    "district",         # sub-region / rayon
    "rooms",
    "living_area_m2",
    "kitchen_area_m2",
    "total_area_m2",
    "floor",
    "total_floors",
    "building_type",
    "layout",
    "build_year",
    "bathroom",
    "furnished",
    "renovation",
    "commission",
    "price",
    "currency",
    "description",
    "date_scraped",
    "url",
]
