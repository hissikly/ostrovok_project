"""Норма осадков по месяцам на сетке над Большим Сочи — для слоя «Осадки» на карте.

Источник: Open-Meteo Historical Weather (ERA5 / ERA5-Land, без ключа), дневные суммы за 2020–2025.
Сетка 0,2° (≈ 16–22 км) от Лазаревского до Красной Поляны: 4 × 7 = 28 точек.
Для каждой точки и месяца: сколько дней с дождём (≥ 1 мм) обычно за неделю, сколько мм за неделю, средний дневной максимум.

Выход: data/seed/climate_rain.json — {source, years, grid: {lats, lons}, months: {"1": [{lat, lon, wet_days, mm, tmax}], …}}
Запуск один раз (≈ 7 мин из-за лимита запросов): python features/climate/pipeline/build_rain.py
"""
import collections
import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LATS = [43.35, 43.55, 43.75, 43.95]
LONS = [39.15, 39.35, 39.55, 39.75, 39.95, 40.15, 40.35]
YEARS = range(2020, 2026)
URL = ("https://archive-api.open-meteo.com/v1/archive?latitude={la}&longitude={lo}&start_date={y}-01-01&end_date={y}-12-31"
       "&daily=precipitation_sum,temperature_2m_max&timezone=Europe%2FMoscow")


def fetch(url):
    for attempt in range(6):
        try:
            return json.load(urllib.request.urlopen(url, timeout=120))
        except Exception as e:  # 429 / обрыв TLS — ждём и повторяем
            print("  повтор:", e)
            time.sleep(30 * (attempt + 1))
    raise RuntimeError("Open-Meteo не ответил")


def main():
    pts = [(a, o) for a in LATS for o in LONS]
    la, lo = ",".join(str(a) for a, _ in pts), ",".join(str(o) for _, o in pts)
    acc = collections.defaultdict(lambda: {"days": 0, "wet": 0, "mm": 0.0, "tmax": 0.0})
    for i, y in enumerate(YEARS):
        if i:
            time.sleep(65)   # лимит Open-Meteo в минуту
        for (a, o), d in zip(pts, fetch(URL.format(la=la, lo=lo, y=y))):
            for t, p, tx in zip(d["daily"]["time"], d["daily"]["precipitation_sum"], d["daily"]["temperature_2m_max"]):
                if p is None or tx is None:
                    continue
                s = acc[(a, o, int(t[5:7]))]
                s["days"] += 1; s["wet"] += p >= 1; s["mm"] += p; s["tmax"] += tx
        print(y, "готово")
    months = {str(m): [{"lat": a, "lon": o,
                        "wet_days": round(acc[(a, o, m)]["wet"] / acc[(a, o, m)]["days"] * 7, 2),
                        "mm": round(acc[(a, o, m)]["mm"] / acc[(a, o, m)]["days"] * 7, 1),
                        "tmax": round(acc[(a, o, m)]["tmax"] / acc[(a, o, m)]["days"], 1)} for a, o in pts]
              for m in range(1, 13)}
    out = {"source": "Open-Meteo Historical Weather (ERA5)", "years": f"{YEARS[0]}–{YEARS[-1]}",
           "per": "неделя (7 дней)", "grid": {"lats": LATS, "lons": LONS}, "months": months}
    (ROOT / "data/seed/climate_rain.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print("data/seed/climate_rain.json:", len(pts), "точек × 12 месяцев")


if __name__ == "__main__":
    main()
