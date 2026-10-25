"""Путь до пляжа по пешеходному графу для всех отелей — факт beach_route.

Вход:  data/seed/hotels.json, data/seed/walk_graph.json.gz (build_walk_graph.py)
Выход: data/seed/facts_beach_route.json — {minutes, back_minutes, meters, up_m, down_m, climb_back_m, steps, underpass, bridge, rail, major_m}
       (up_m/down_m — набор и сброс высоты по дороге к пляжу; climb_back_m = down_m — сколько в гору обратно)

В отличие от beach_distance (по прямой) — реальный путь по улицам и тропам, время по Тоблеру
в обе стороны: «7 мин вниз, обратно 11 в гору». Линию маршрута сервис строит заново по запросу.

python features/beach_route/pipeline/beach_route.py
"""
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from core.walk import graph, to_beach  # noqa: E402
from features.hotels.backend import hotels as all_hotels  # noqa: E402  — точка отеля как на карте


def main():
    g = graph()
    today = dt.date.today()
    facts, miss = [], 0
    for h in all_hotels():
        r = to_beach(h["lat"], h["lon"])
        if r is None:
            miss += 1
            continue
        f = r["flags"]
        facts.append({
            "hotel_id": h["id"], "scope": "hotel", "characteristic": "beach_route",
            "value": {"minutes": r["minutes"], "back_minutes": r["back_minutes"], "meters": r["meters"],
                      "up_m": r["up_m"], "down_m": r["down_m"],
                      # подъём на обратном пути с пляжа = спуск по дороге туда
                      "climb_back_m": r["down_m"], "steps": f["steps"], "underpass": f["underpass"],
                      "bridge": f["bridge"], "rail": f["rail"], "major_m": f["major_m"]},
            # путь по OSM надёжен, подъём — по модели поверхности (крыши/кроны), отсюда не 0,9
            "confidence": 0.75, "source": "computed:walk-graph", "method_version": "walk-tobler@0.1",
            "evidence": {"osm": "highway=* пешеходная сеть", "dem": "Copernicus GLO-30, минимум 3×3",
                         "method": "кратчайший по времени путь до пляжа/берега, Тоблер туда и обратно"},
            "obtained_at": g.obtained_at or today.isoformat(),
            "valid_until": (today + dt.timedelta(days=365)).isoformat(), "status": "active",
        })
    out = ROOT / "data/seed/facts_beach_route.json"
    json.dump(facts, open(out, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"{out.relative_to(ROOT)}: {len(facts)} отелей, без маршрута {miss}")


if __name__ == "__main__":
    main()
