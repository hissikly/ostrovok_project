"""Метрика: насколько точно разбор (без LLM) раскладывает свободный ответ отельера по полям.

Размеченная выборка — features/hotelier/eval_answers.json (25 ответов, 55 полей, написаны командой).
Точность = доля полей, где разбор совпал с разметкой; «лишние» поля (разбор нашёл то, чего нет в разметке) — отдельно.

python features/hotelier/pipeline/eval_parse.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from features.hotelier.backend.parse import parse  # noqa: E402
from features.knowledge.backend import topics  # noqa: E402


def main():
    T = {t["id"]: t for t in topics()}
    cases = json.load(open(ROOT / "features/hotelier/eval_answers.json", encoding="utf-8"))
    ok = total = extra = 0
    for c in cases:
        got = {f["id"]: f["value"] for f in parse(T[c["topic"]], c["text"]) if f["value"] not in (None, "") and f["type"] != "text"}
        for k, v in c["expect"].items():
            total += 1
            if got.get(k) == v:
                ok += 1
            else:
                print(f"  ✗ {c['topic']}.{k}: ждали {v!r}, получили {got.get(k)!r} — «{c['text']}»")
        extra += len(set(got) - set(c["expect"]))
    print(f"Точность разбора: {ok}/{total} полей = {ok / total:.0%}; лишних полей: {extra}; ответов: {len(cases)}")


if __name__ == "__main__":
    main()
