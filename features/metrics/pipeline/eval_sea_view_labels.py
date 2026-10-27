"""Вид на море: точность и калибровка уверенности на ручной разметке (features/metrics/labels/sea_view.csv).

Разметка слепая: в таблице нет нашего ответа, только отель и ссылки — человек смотрит фото номеров и панорамы
и пишет, видно ли море из номеров. Наш ответ по отелю берём из data/seed/facts_okno.json:
  да      — хотя бы с одной стороны море в окне (from_floor);
  краешек — только краешек моря (glimpse_from);
  нет     — моря не видно ни с одной стороны.
Выборка (--make): 10 «да», 7 «краешек», 8 «нет», внутри — разная уверенность; порядок перемешан.

  python features/metrics/pipeline/eval_sea_view_labels.py --make   # создать пустую таблицу (не затирает заполненную)
  python features/metrics/pipeline/eval_sea_view_labels.py          # посчитать по заполненной
"""
import collections
import csv
import hashlib
import json
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LABELS = ROOT / "features/metrics/labels/sea_view.csv"
COLS = ["№", "hotel_id", "Название", "Адрес", "Сайт", "Карта", "Видно море (да / краешек / нет / ?)",
        "Откуда узнали (ссылка)", "Комментарий"]
ANSWER = COLS[6]
QUOTA = {"да": 10, "краешек": 7, "нет": 8}


def ours() -> dict:
    """hotel_id → (наш ответ, уверенность)."""
    hotels = {h["id"] for h in json.loads((ROOT / "data/seed/hotels.json").read_text())}
    by = collections.defaultdict(list)
    for f in json.loads((ROOT / "data/seed/facts_okno.json").read_text()):
        if f["characteristic"] == "sea_view" and f["hotel_id"] in hotels:
            by[f["hotel_id"]].append(f)
    out = {}
    for h, fs in by.items():
        v = "да" if any(f["value"].get("from_floor") for f in fs) else \
            "краешек" if any(f["value"].get("glimpse_from") for f in fs) else "нет"
        out[h] = (v, max(f["confidence"] for f in fs))
    return out


def make():
    if LABELS.exists():
        sys.exit(f"{LABELS} уже есть — не затираю")
    hotels = {h["id"]: h for h in json.loads((ROOT / "data/seed/hotels.json").read_text())}
    pred = ours()
    picked = []
    for v, n in QUOTA.items():
        ids = sorted((h for h, (p, _) in pred.items() if p == v), key=lambda h: pred[h][1])
        step = len(ids) / n            # равномерно по уверенности — от самых неуверенных до самых уверенных
        picked += [ids[int(i * step)] for i in range(n)]
    picked.sort(key=lambda h: hashlib.md5(h.encode()).hexdigest())
    LABELS.parent.mkdir(parents=True, exist_ok=True)
    with open(LABELS, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(COLS)
        for i, h in enumerate(picked, 1):
            x = hotels[h]
            w.writerow([i, h, x["name"] or x["kind_ru"], x.get("address") or "", x.get("website") or "",
                        "https://yandex.ru/maps/?" + urllib.parse.urlencode(        # карточка места с фото и отзывами
                            {"text": f"{x['name'] or x['kind_ru']} Сочи", "ll": f"{x['lon']},{x['lat']}", "z": 18}),
                        "", "", ""])
    print(f"{LABELS.relative_to(ROOT)}: {len(picked)} отелей")


def evaluate():
    pred = ours()
    rows = list(csv.DictReader(open(LABELS, encoding="utf-8-sig"), delimiter=";"))
    lab = [(r["hotel_id"], r[ANSWER].strip().lower()) for r in rows if r[ANSWER].strip().lower() in QUOTA]
    if not lab:
        sys.exit("В таблице пока нет ответов «да / краешек / нет»")
    sea = lambda v: v != "нет"                       # «краешек» считаем «море видно»
    hit = [(sea(pred[h][0]) == sea(t), pred[h][1], pred[h][0], t) for h, t in lab]
    exact = sum(pred[h][0] == t for h, t in lab)
    print(f"Размечено {len(lab)} из {len(rows)} (ещё «?» или пусто: {len(rows) - len(lab)})")
    print(f"Видно ли море (да/краешек против нет): верно {sum(h[0] for h in hit)} из {len(hit)} "
          f"({100 * sum(h[0] for h in hit) / len(hit):.0f}%); точный класс: {exact} из {len(lab)}")
    tab = collections.Counter((p, t) for _, _, p, t in hit)
    print("Наш ответ → разметка: " + ", ".join(f"{p}→{t}: {n}" for (p, t), n in sorted(tab.items())))
    print("Калибровка (уверенность расчёта → доля верных):")
    for lo, hi in ((0, 0.55), (0.55, 0.65), (0.65, 1.01)):
        b = [ok for ok, c, _, _ in hit if lo <= c < hi]
        if b:
            print(f"  {lo:.2f}–{min(hi, 1):.2f}: {sum(b)} из {len(b)} верно ({100 * sum(b) / len(b):.0f}%), "
                  f"средняя уверенность {sum(c for ok, c, _, _ in hit if lo <= c < hi) / len(b):.2f}")


if __name__ == "__main__":
    make() if "--make" in sys.argv else evaluate()
