"""Время пешком от каждого отеля до каждого места подборки (до 60 мин) — по пешеходному графу.

Вход:  features/sights/sights.json, data/seed/hotels.json, data/seed/walk_graph.json.gz
Выход: data/seed/sights_walk.json — {sight_id: {hotel_id: [секунды, метры]}}

Считаем «обратной» Дейкстрой от места: одна на место, а время — именно «от отеля до места»
(по Тоблеру вверх и вниз по-разному). Место вне графа (Роза Хутор) или дальше часа пешком —
в сервисе честная оценка «на машине» по прямой.

python features/sights/pipeline/sight_times.py
"""
import heapq
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from core.walk import SNAP_SPEED, graph  # noqa: E402
from features.hotels.backend import hotels as all_hotels  # noqa: E402

CUTOFF_S = 60 * 60


def _snap(g, lat, lon):
    n = g.nearest(lat, lon)
    if n is None:
        return None, 0.0
    return n, math.hypot((lon - g.lon[n]) * 80_900, (lat - g.lat[n]) * 110_540)


def to_target(g, t):
    """Время и путь в метрах от всех узлов до t в пределах CUTOFF_S (идём по рёбрам в обратную сторону)."""
    best, meters = {t: 0.0}, {t: 0.0}
    pq, done = [(0.0, t)], set()
    while pq:
        gv, v = heapq.heappop(pq)
        if v in done:
            continue
        done.add(v)
        for u, k, fwd in g.adj[v]:
            # ребро k из v в u «прямое», если fwd; гость идёт из u в v — значит, в обратную сторону
            nu = gv + g._cost(k, not fwd)
            if nu <= CUTOFF_S and nu < best.get(u, math.inf):
                best[u], meters[u] = nu, meters[v] + g.edges[k][2]
                heapq.heappush(pq, (nu, u))
    return best, meters


def main():
    g = graph()
    sights = json.load(open(ROOT / "features/sights/sights.json", encoding="utf-8"))
    hotels = all_hotels()
    starts = {h["id"]: _snap(g, h["lat"], h["lon"]) for h in hotels}
    out = {}
    for s in sights:
        t, t_off = _snap(g, s["lat"], s["lon"])
        row = {}
        if t is not None:
            best, meters = to_target(g, t)
            for hid, (n, off) in starts.items():
                if n in best:
                    sec = best[n] + (off + t_off) / SNAP_SPEED
                    if sec <= CUTOFF_S:
                        row[hid] = [round(sec), round(meters[n] + off + t_off)]
        out[s["id"]] = row
        near = min((v[0] for v in row.values()), default=None)
        print(f"  {s['id']}: {len(row)} отелей в часе пешком, ближайший {round(near / 60) if near else '—'} мин")
    path = ROOT / "data/seed/sights_walk.json"
    json.dump(out, open(path, "w"), separators=(",", ":"))
    print(f"{path.relative_to(ROOT)}: {path.stat().st_size / 1e3:.0f} КБ")


if __name__ == "__main__":
    main()
