"""Запросы к Overpass API с повторами и запасными серверами."""
import json
import sys
import time

import requests

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
HEADERS = {"User-Agent": "ostrovok-hackathon-okno/0.1 (research prototype)"}


def query(q: str, tries: int = 12, timeout: int = 300) -> dict:
    last = None
    for i in range(tries):
        ep = ENDPOINTS[i % len(ENDPOINTS)]
        try:
            r = requests.post(ep, data={"data": q}, headers=HEADERS, timeout=timeout)
            if r.status_code == 200 and r.text.lstrip().startswith("{"):
                return r.json()
            last = f"{ep}: HTTP {r.status_code} {r.text[:120]!r}"
        except requests.RequestException as e:
            last = f"{ep}: {type(e).__name__}"
        print(f"  попытка {i + 1}: {last}", file=sys.stderr)
        time.sleep(min(2 + i * 2, 15))
    raise RuntimeError(f"Overpass недоступен: {last}")


if __name__ == "__main__":
    q, out = sys.argv[1], sys.argv[2]
    data = query(open(q).read())
    json.dump(data, open(out, "w"), ensure_ascii=False)
    print(f"{out}: {len(data.get('elements', []))} элементов")
