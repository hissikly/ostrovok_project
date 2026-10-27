"""Метрика «было / стало»: насколько наш подбор меняет выбор по сравнению с обычной выдачей сайта.

Запросы — все сочетания 1–3 главных линз (вид на море, закат, пляж рядом, не в гору, тишина) и несколько
с «что рядом». Для каждого: обычная выдача (рейтинг, «до моря по прямой») против нашей (по фактам).
Считаем: в скольких запросах меняется топ-3, сколько подвохов («нет» по фактам) в первой десятке
обычной выдачи и в скольких запросах подвох есть уже в её топ-3.

Запуск: python features/compare/pipeline/eval_baseline.py  (печатает таблицу для README)
"""
import itertools
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from features.compare.backend import baseline  # noqa: E402
from features.search.backend.ranking import search  # noqa: E402

PRIMARY = ["sea_view", "sunset", "beach_near", "flat", "quiet"]
EXTRA = [["quiet", "near_grocery"], ["beach_near", "near_playground"], ["sea_view", "near_pharmacy_24"],
         ["quiet", "sea_view", "near_cafe"], ["flat", "near_bus"]]
CTX = {"month": 5}


def queries():
    for k in (1, 2, 3):
        yield from (list(c) for c in itertools.combinations(PRIMARY, k))
    yield from EXTRA


def main():
    rows = []
    for q in queries():
        ours = [r["id"] for r in search(q, CTX)["hotels"][:3]]
        b = baseline(q, CTX, top=10)
        base3 = [h["id"] for h in b["hotels"][:3]]
        rows.append({"q": q, "changed": set(ours) != set(base3), "same": len(set(ours) & set(base3)),
                     "traps10": b["summary"]["traps"], "trap3": any(h["traps"] for h in b["hotels"][:3]),
                     "unknown10": b["summary"]["unknown"]})
    n = len(rows)
    changed = sum(r["changed"] for r in rows)
    trap3 = sum(r["trap3"] for r in rows)
    with_traps = sum(r["traps10"] > 0 for r in rows)
    avg_traps = sum(r["traps10"] for r in rows) / n
    print(f"Запросов: {n} (все сочетания 1–3 главных линз + {len(EXTRA)} с «что рядом»), месяц — май")
    print(f"| Метрика | Значение |\n|---|---|")
    print(f"| Топ-3 отличается от обычной выдачи | {changed} из {n} ({changed / n:.0%}) |")
    print(f"| В первой десятке обычной выдачи есть подвох | {with_traps} из {n} ({with_traps / n:.0%}) |")
    print(f"| Подвох уже в топ-3 обычной выдачи | {trap3} из {n} ({trap3 / n:.0%}) |")
    print(f"| Подвохов в первой десятке в среднем | {avg_traps:.1f} |")
    print("\nПо запросам (подвохов в десятке / совпало в топ-3):")
    for r in rows:
        print(f"  {'+'.join(r['q']):40s} подвохов {r['traps10']}, совпало {r['same']} из 3")


if __name__ == "__main__":
    main()
