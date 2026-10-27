"""Покрытие и доля вопросов к отельеру: агент характеристик (features/characteristics) на всех отелях.

Для каждой пары (отель × характеристика) агент идёт по плану спеки, как в сервисе, но вопросы отелям не задаёт.
Итог пары — одно из трёх:
  надёжно   — источник ответил с уверенностью ≥ порога спеки (min_confidence);
  слабо     — ответ есть, но ниже порога: показываем с честной низкой уверенностью;
  к отелю   — открытые данные молчат (или ответ ниже порога): последний шаг плана — вопрос отельеру.
Покрытие = надёжно / все пары; доля вопросов к отельеру = (слабо + к отелю) / все пары.
Без LLM и сети. Запуск: python features/metrics/pipeline/eval_coverage.py [--md]
"""
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from features.characteristics.backend.planner import research  # noqa: E402
from features.characteristics.backend.spec import builtin  # noqa: E402


def main(md: bool = False):
    hotels = json.loads((ROOT / "data/seed/hotels.json").read_text())
    rows, total = [], collections.Counter()
    for spec in builtin():
        c = collections.Counter()
        for h in hotels:
            r = research(h, spec, ask=False)
            f = r["fact"]
            c["reliable" if f and f["confidence"] >= spec["min_confidence"] else "weak" if f else "ask"] += 1
        n = sum(c.values())
        total.update(c)
        rows.append((spec, c, n))

    core = [r for r in rows if r[0]["kind"] != "near"]
    near = [r for r in rows if r[0]["kind"] == "near"]
    pct = lambda a, b: f"{100 * a / b:.0f}%"
    out = []
    if md:
        out += ["| Характеристика | Надёжно (покрытие) | Слабо | Нет данных | Вопрос отелю |", "|---|---|---|---|---|"]
        for spec, c, n in core:
            out.append(f"| {spec['title']} | {c['reliable']} ({pct(c['reliable'], n)}) | {c['weak']} | {c['ask']} | "
                       f"{pct(c['weak'] + c['ask'], n)} |")
        cc = sum((r[1] for r in core), collections.Counter())
        cn = sum(r[2] for r in core)
        out.append(f"| **{len(core)} основных вместе** | **{pct(cc['reliable'], cn)}** | {cc['weak']} | {cc['ask']} | "
                   f"**{pct(cc['weak'] + cc['ask'], cn)}** |")
        nc = sum((r[1] for r in near), collections.Counter())
        nn = sum(r[2] for r in near)
        out.append(f"| «Что рядом», {len(near)} фильтров вместе | {pct(nc['reliable'], nn)} | {nc['weak']} | {nc['ask']} | "
                   f"{pct(nc['weak'] + nc['ask'], nn)} |")
    else:
        for spec, c, n in rows:
            out.append(f"{spec['id']:<24} надёжно {c['reliable']:>4} · слабо {c['weak']:>4} · к отелю {c['ask']:>4} из {n}")
    n = sum(total.values())
    out.append(f"\nВсего пар {n} ({len(hotels)} отелей × {len(rows)} характеристик): покрытие "
               f"{pct(total['reliable'], n)}, доля вопросов к отельеру {pct(total['weak'] + total['ask'], n)}")
    print("\n".join(out))


if __name__ == "__main__":
    main("--md" in sys.argv)
