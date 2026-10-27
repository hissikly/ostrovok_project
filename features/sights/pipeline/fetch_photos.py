"""Фото мест из Wikimedia Commons — один раз, офлайн; в рантайме сеть не нужна.

Вход:  features/sights/sights.json — у каждого места имя файла на Commons (поле photo), выбрано вручную
Выход: data/seed/sights/<id>.jpg (960 px по ширине) и data/seed/sights/photos.json —
       автор, лицензия и ссылка на страницу файла (подпись под фото и раздел README «Сторонние компоненты»)

Берём только свободные лицензии (CC0, Public domain, CC BY, CC BY-SA). Запросы — через curl,
по одному в 2 с, с User-Agent по правилам Wikimedia.

python features/sights/pipeline/fetch_photos.py
"""
import html
import json
import re
import subprocess
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data/seed/sights"
API = "https://commons.wikimedia.org/w/api.php"
UA = "OknoHackathon/0.1 (https://github.com/ostrovok-hackathon-2026/vot-takaya-vot-komanda-sobachka)"
FREE = ("CC0", "Public domain", "CC BY")
WIDTH = 960


def _get(url, path=None):
    for _ in range(5):
        cmd = ["curl", "-s", "-L", "-m", "60", "-A", UA, url] + (["-o", str(path)] if path else [])
        r = subprocess.run(cmd, capture_output=True, text=not path)
        if path and path.exists() and path.stat().st_size > 5000:
            return True
        if not path and r.stdout.startswith("{"):
            return json.loads(r.stdout)
        time.sleep(4)
    raise RuntimeError(f"не скачалось: {url}")


def _text(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def main():
    sights = json.load(open(ROOT / "features/sights/sights.json", encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    credits = {}
    for s in sights:
        q = urllib.parse.urlencode({"action": "query", "format": "json", "titles": s["photo"], "prop": "imageinfo",
                                    "iiprop": "url|extmetadata", "iiurlwidth": WIDTH})
        page = next(iter(_get(f"{API}?{q}")["query"]["pages"].values()))
        ii = page["imageinfo"][0]
        meta = ii["extmetadata"]
        lic = meta.get("LicenseShortName", {}).get("value", "")
        if not lic.startswith(FREE):
            raise SystemExit(f"{s['id']}: лицензия «{lic}» не свободная — выберите другой файл")
        _get(ii["thumburl"], OUT / f"{s['id']}.jpg")
        credits[s["id"]] = {"file": s["photo"], "author": _text(meta.get("Artist", {}).get("value")) or "неизвестен",
                            "license": lic, "license_url": meta.get("LicenseUrl", {}).get("value"),
                            "page": ii["descriptionurl"]}
        print(f"  {s['id']}: {lic}, {credits[s['id']]['author'][:40]}")
        time.sleep(2)
    json.dump(credits, open(OUT / "photos.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    size = sum(p.stat().st_size for p in OUT.glob("*.jpg")) / 1e6
    print(f"{OUT.relative_to(ROOT)}: {len(credits)} фото, {size:.1f} МБ")


if __name__ == "__main__":
    main()
