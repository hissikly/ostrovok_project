"""Шум днём и ночью у каждой стороны здания — факт noise.

Вход:  data/raw/noise_sources.json (extract_sources.py), data/seed/okno/*.json (стороны здания:
       середина фасада и куда он смотрит), data/seed/hotels.json
Выход: data/seed/facts_noise.json

Это инженерная оценка по карте, не замер — уверенность 0,5, и так и пишем в интерфейсе.
- Уровень источника (дБА, Leq) на 10 м, день/ночь: трасса 74/67, главная улица 71/63, второстепенная 67/59,
  улица 62/53, ж/д 70/66; бар/паб — ночью 65 (днём 55), ночной клуб — ночью 75; аэропорт — 85 дБ
  на 100 м от полосы днём, ночью на 6 меньше.
- Затухание: линия −10·lg(d/10), точка −20·lg(d/10), плюс городское (дома, земля) −0,02 дБ/м
  после 20 м, не больше 15 дБ.
- Сторона здания: источник за спиной фасада (угол > 100°) −12 дБ — закрывает своё здание; 70–100° −4 дБ.
  Соседние дома как экран не учитываем — поэтому оценка скорее с запасом в сторону «шумнее».
- Уровни ночью у фасада: ≤45 тихо, ≤55 спокойно, ≤62 шумно, выше — очень шумно (ориентир — нормы ВОЗ
  для ночного шума у дома, 40–45 дБ).

python features/noise/pipeline/noise.py
"""
import datetime as dt
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SEED = ROOT / "data/seed"
LAT0 = 43.58
M_LAT, M_LON = 110_540, 111_320 * math.cos(math.radians(LAT0))
LINE_REF = {"trunk": (74, 67), "motorway": (76, 70), "primary": (71, 63), "secondary": (67, 59),
            "tertiary": (62, 53), "rail": (70, 66)}
POINT_REF = {"bar": (55, 65), "pub": (55, 65), "nightclub": (50, 75)}
RUNWAY_REF = (85, 79)                                    # на 100 м
RADIUS = {"runway": 4000, "line": 700, "point": 300}
KIND_RU = {"trunk": "трасса", "motorway": "трасса", "primary": "оживлённая улица", "secondary": "оживлённая улица",
           "tertiary": "улица", "rail": "железная дорога", "runway": "аэропорт", "bar": "бар", "pub": "паб",
           "nightclub": "ночной клуб"}
CELL = 250


def xy(lat, lon):
    return lon * M_LON, lat * M_LAT


def seg_dist(px, py, ax, ay, bx, by):
    """Расстояние от точки до отрезка и ближайшая точка на нём."""
    dx, dy = bx - ax, by - ay
    t = 0 if dx == dy == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy), cx, cy


def excess(d):
    return min(15.0, max(0.0, 0.02 * (d - 20)))


def shield(normal_az, px, py, sx, sy):
    if normal_az is None:
        return 0.0
    bearing = math.degrees(math.atan2(sx - px, sy - py)) % 360
    a = abs((bearing - normal_az + 180) % 360 - 180)
    return 12.0 if a > 100 else 4.0 if a > 70 else 0.0


def level_word(night):
    return "quiet" if night <= 45 else "calm" if night <= 55 else "noisy" if night <= 62 else "very_noisy"


class Sources:
    def __init__(self, d):
        self.segs = defaultdict(list)       # (cell) -> [(ax, ay, bx, by, line_idx)]
        self.lines = [l for l in d["lines"] if not l["tunnel"]]
        for i, l in enumerate(self.lines):
            pts = [xy(a, b) for a, b in l["pts"]]
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                for c in {(int(ax // CELL), int(ay // CELL)), (int(bx // CELL), int(by // CELL))}:
                    self.segs[c].append((ax, ay, bx, by, i))
        self.points = [(xy(p["lat"], p["lon"]), p) for p in d["points"]]
        # настоящие полосы аэропорта; короткие «runway» в OSM — вертолётные площадки, их не считаем
        self.runways = [i for i, l in enumerate(self.lines) if l["kind"] == "runway" and self._length(l) > 1500]

    @staticmethod
    def _length(l):
        pts = [xy(a, b) for a, b in l["pts"]]
        return sum(math.hypot(bx - ax, by - ay) for (ax, ay), (bx, by) in zip(pts, pts[1:]))

    def at(self, lat, lon, normal_az=None):
        px, py = xy(lat, lon)
        best = {}                           # линия -> (расстояние, x, y): ближайшая точка каждой линии
        r = RADIUS["line"]
        cx, cy = int(px // CELL), int(py // CELL)
        k = r // CELL + 1
        for i in range(cx - k, cx + k + 1):
            for j in range(cy - k, cy + k + 1):
                for ax, ay, bx, by, li in self.segs.get((i, j), ()):
                    if self.lines[li]["kind"] == "runway":
                        continue
                    d, sx, sy = seg_dist(px, py, ax, ay, bx, by)
                    if d <= r and (li not in best or d < best[li][0]):
                        best[li] = (d, sx, sy)
        contrib = []                        # (день, ночь, вид, имя, расстояние)
        for li, (d, sx, sy) in best.items():
            l = self.lines[li]
            d = max(d, 5.0)
            day, night = LINE_REF[l["kind"]]
            loss = 10 * math.log10(d / 10) + excess(d) + shield(normal_az, px, py, sx, sy)
            contrib.append((day - loss, night - loss, l["kind"], l["name"], d))
        for li in self.runways:
            pts = [xy(a, b) for a, b in self.lines[li]["pts"]]
            d, sx, sy = min(seg_dist(px, py, *pts[n], *pts[n + 1]) for n in range(len(pts) - 1))
            if d <= RADIUS["runway"]:
                d = max(d, 100.0)
                loss = 20 * math.log10(d / 100) + shield(normal_az, px, py, sx, sy) / 2   # самолёт над головой
                contrib.append((RUNWAY_REF[0] - loss, RUNWAY_REF[1] - loss, "runway", "", d))
        for (sx, sy), p in self.points:
            d = math.hypot(px - sx, py - sy)
            if d <= RADIUS["point"]:
                d = max(d, 5.0)
                day, night = POINT_REF[p["kind"]]
                loss = 20 * math.log10(d / 10) + excess(d) + shield(normal_az, px, py, sx, sy)
                contrib.append((day - loss, night - loss, p["kind"], p["name"], d))
        if not contrib:
            return {"day_db": 40, "night_db": 35, "level": "quiet", "source": None}
        esum = lambda vals: 10 * math.log10(sum(10 ** (v / 10) for v in vals))
        day, night = esum(c[0] for c in contrib), esum(c[1] for c in contrib)
        top = max(contrib, key=lambda c: c[1])
        return {"day_db": round(max(day, 40)), "night_db": round(max(night, 35)), "level": level_word(night),
                "source": {"kind": top[2], "kind_ru": KIND_RU[top[2]], "name": top[3], "meters": round(top[4])}}


def main():
    src = Sources(json.load(open(ROOT / "data/raw/noise_sources.json")))
    today = dt.date.today()
    facts = []
    by_level = defaultdict(int)

    def fact(hid, scope, v, conf):
        by_level[v["level"]] += 1
        facts.append({"hotel_id": hid, "scope": scope, "characteristic": "noise", "value": v, "confidence": conf,
                      "source": "computed:noise-model", "method_version": "noise@0.1",
                      "evidence": {"osm": "дороги по классу, ж/д, взлётная полоса, бары/клубы",
                                   "method": "Leq по классу источника, затухание с расстоянием, экран своего здания"},
                      "obtained_at": today.isoformat(), "valid_until": (today + dt.timedelta(days=180)).isoformat(),
                      "status": "active"})

    with_sides = set()
    for path in sorted((SEED / "okno").glob("*.json")):
        d = json.load(open(path))
        for side, f in d["facades"].items():
            fact(d["hotel_id"], f"facade:{side}", src.at(f["eye"][0], f["eye"][1], f["normal_az"]), 0.5)
        with_sides.add(d["hotel_id"])
    for h in json.load(open(SEED / "hotels.json")):
        if h["id"] not in with_sides:   # без контура здания — стороны неизвестны, оценка у точки отеля
            fact(h["id"], "hotel", src.at(h["lat"], h["lon"]), 0.4)
    out = SEED / "facts_noise.json"
    json.dump(facts, open(out, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"{out.relative_to(ROOT)}: {len(facts)} фактов, по сторонам у {len(with_sides)} отелей; ночью {dict(by_level)}")


if __name__ == "__main__":
    main()
