"""Знания верхних уровней (страна → край → город) для базы частых вопросов.

Что кладём и откуда:
- swim         Сочи — температура моря по месяцам: Open-Meteo Marine, среднее за 2023–2025
- beach_type   Сочи — какой берег у пляжей: OSM natural=beach + surface (data/raw/osm_coast.json)
- tourist_tax  Сочи — туристический налог: Налоговый кодекс РФ, гл. 33.1 (ставка вписана руками, с источником)

Выход: data/seed/knowledge.json — [{path, topic, value, text, source, confidence, obtained_at, valid_until, evidence}]

python features/knowledge/pipeline/build_knowledge.py
"""
import collections
import datetime as dt
import json
import statistics
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOCHI = "ru/krd/sochi"
MARINE = ("https://marine-api.open-meteo.com/v1/marine?latitude=43.58&longitude=39.70"
          "&start_date=2023-01-01&end_date=2025-12-31&daily=sea_surface_temperature_mean&timezone=Europe/Moscow")
PEBBLE = {"pebblestone", "gravel", "stone", "shingle", "rock"}


def swim(today):
    d = json.load(urllib.request.urlopen(MARINE, timeout=60))
    by = collections.defaultdict(list)
    for t, v in zip(d["daily"]["time"], d["daily"]["sea_surface_temperature_mean"]):
        if v is not None:
            by[int(t[5:7])].append(v)
    months = {m: round(statistics.mean(v), 1) for m, v in sorted(by.items())}
    warm = [m for m, t in months.items() if t >= 20]
    return {"path": SOCHI, "topic": "swim", "value": {"sea_c": months, "warm_months": warm},
            "text": "Море теплее 20° с июня по октябрь" if warm == [6, 7, 8, 9, 10] else f"Море теплее 20° в месяцы {warm}",
            "source": "open-meteo", "confidence": 0.85, "obtained_at": today,
            "valid_until": (dt.date.fromisoformat(today) + dt.timedelta(days=365)).isoformat(),
            "evidence": {"api": "Open-Meteo Marine, sea_surface_temperature_mean", "years": "2023–2025",
                         "point": [43.58, 39.70]}}


def beach_type(today):
    beaches = [e for e in json.load(open(ROOT / "data/raw/osm_coast.json"))["elements"]
               if e.get("tags", {}).get("natural") == "beach"]
    tagged = [e["tags"]["surface"] for e in beaches if "surface" in e["tags"]]
    pebble = sum(s in PEBBLE for s in tagged)
    sand = sum(s == "sand" for s in tagged)
    return {"path": SOCHI, "topic": "beach_type", "value": {"surface": "галька" if pebble > sand else "песок"},
            "text": "Пляжи в Сочи в основном галечные",
            # размечена только часть пляжей — уверенность средняя
            "source": "osm", "confidence": round(0.5 + 0.3 * len(tagged) / max(1, len(beaches)), 2),
            "obtained_at": today, "valid_until": (dt.date.fromisoformat(today) + dt.timedelta(days=365)).isoformat(),
            "evidence": {"osm": "natural=beach + surface", "beaches": len(beaches), "with_surface": len(tagged),
                         "pebble": pebble, "sand": sand}}


def tourist_tax(today):
    return {"path": SOCHI, "topic": "tourist_tax", "value": {"rate_pct": 2, "min_rub": 100},
            "text": "Туристический налог 2% от стоимости проживания, но не меньше 100 ₽ за сутки",
            "source": "law", "confidence": 0.8, "obtained_at": today, "valid_until": "2026-12-31",
            "evidence": {"law": "Налоговый кодекс РФ, гл. 33.1 «Туристический налог»: 2025 — 1%, 2026 — 2%, 2027 — 3%",
                         "links": ["https://www.tourdom.ru/hotline/obzory-i-analitika/turisticheskiy-nalog-2026-gde-i-skolko-platit/",
                                   "https://www.osnmedia.ru/obshhestvo/turisticheskij-nalog-v-sochi-prines-1-065-mlrd-rublej-v-2025-godu/"]}}


def main():
    today = dt.date.today().isoformat()
    items = [tourist_tax(today), beach_type(today)]
    try:
        items.append(swim(today))
    except Exception as e:  # сеть недоступна — оставляем прошлую выгрузку
        old = {(k["path"], k["topic"]): k for k in json.load(open(ROOT / "data/seed/knowledge.json"))} \
            if (ROOT / "data/seed/knowledge.json").exists() else {}
        if (SOCHI, "swim") in old:
            items.append(old[(SOCHI, "swim")])
        print(f"Open-Meteo недоступен ({e}), температура моря — из прошлой выгрузки")
    out = ROOT / "data/seed/knowledge.json"
    json.dump(items, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{out.relative_to(ROOT)}: {len(items)} знаний")


if __name__ == "__main__":
    main()
