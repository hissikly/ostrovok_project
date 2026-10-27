"""Точность посчитанных характеристик: сверка с тем, что отели сами пишут на своих сайтах.

Разметка — цитаты с официальных сайтов (data/seed/facts_web.json: web:beach_claim, web:sea_view), их собирали
отдельно от расчёта (features/web_sources), поэтому это независимая проверка. Оговорки:
  — сайт отеля не истина: «5 минут до моря» — часто реклама; поэтому для минут меряем, насколько отель занижает;
  — про вид на море сайты пишут только «есть», отказов в выборке нет — меряем полноту, а не точность «нет».
Запуск: python features/metrics/pipeline/eval_accuracy.py
"""
import collections
import json
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def load(name):
    return json.loads((ROOT / "data/seed" / name).read_text())


def by_hotel(rows, char):
    out = collections.defaultdict(list)
    for f in rows:
        if f["characteristic"] == char:
            out[f["hotel_id"]].append(f)
    return out


def beach(web):
    straight = {f["hotel_id"]: f["value"]["meters"] for f in load("facts_beach.json")}
    route = {f["hotel_id"]: f["value"] for f in load("facts_beach_route.json")}
    meters, minutes, first = [], [], []
    for f in web:
        if f["characteristic"] != "web:beach_claim":
            continue
        h, c = f["hotel_id"], f["value"]
        if c.get("meters"):
            meters.append((c["meters"], straight[h]))
        if c.get("walk_min") and h in route:
            minutes.append((c["walk_min"], route[h]["minutes"]))
        if c.get("first_line") and h in route:
            first.append(route[h]["meters"])
    near = [abs(o - c) <= max(50, 0.3 * c) for c, o in meters]
    print(f"До моря по прямой — сверка с «N м до моря» на сайте отеля, {len(meters)} отелей:")
    print(f"  совпадает (±30%, не меньше ±50 м): {sum(near)} из {len(meters)} ({100 * sum(near) / len(meters):.0f}%), "
          f"медианная ошибка {st.median(abs(o - c) for c, o in meters):.0f} м")
    ok = [abs(o - c) <= 3 for c, o in minutes]
    under = [o >= 1.5 * c for c, o in minutes]
    print(f"Минуты пешком — сверка с «N мин до моря» на сайте, {len(minutes)} отелей:")
    print(f"  совпадает (±3 мин): {sum(ok)} из {len(minutes)} ({100 * sum(ok) / len(minutes):.0f}%); "
          f"по нашему маршруту в 1,5+ раза дольше обещанного: {sum(under)} ({100 * sum(under) / len(minutes):.0f}%); "
          f"медиана: обещано {st.median(c for c, _ in minutes):.0f} мин, по маршруту {st.median(o for _, o in minutes):.0f} мин")
    print(f"«Первая линия» на сайте, {len(first)} отелей: пешком до пляжа ≤ 400 м у {sum(m <= 400 for m in first)}")


def sea_view(web):
    ours = by_hotel(load("facts_okno.json"), "sea_view")
    claims = [h for h in by_hotel(web, "web:sea_view") if h in ours]
    seen = lambda fs, key: any(f["value"].get(k) for f in fs for k in key)
    rate = lambda key, hs: sum(seen(ours[h], key) for h in hs)
    for title, key in (("хотя бы краешек моря", ("from_floor", "glimpse_from")), ("море в окне", ("from_floor",))):
        print(f"Вид на море ({title}): найден у {rate(key, claims)} из {len(claims)} отелей, которые пишут о виде на сайте; "
              f"для сравнения — у {100 * rate(key, ours) / len(ours):.0f}% всех {len(ours)} посчитанных отелей")
    conf = [f["confidence"] for h in claims for f in ours[h]]
    print(f"  уверенность расчёта у этих отелей: {min(conf):.2f}–{max(conf):.2f}; калибровку на {len(claims)} "
          f"отелях без отказов не оцениваем — нужна ручная разметка с «нет»")


if __name__ == "__main__":
    web = load("facts_web.json")
    beach(web)
    sea_view(web)
