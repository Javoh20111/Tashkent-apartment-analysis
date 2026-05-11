import requests
from bs4 import BeautifulSoup

url = "https://uybozortv.uz/property-info/duplex-kvartira-mp19j3en"

html = requests.get(url).text
print(html[:500])