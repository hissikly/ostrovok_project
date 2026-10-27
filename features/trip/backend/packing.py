"""Чемодан из фактов: правила — данными в features/trip/packing.json, здесь только их исполнение.

Пункт появляется, только если все его условия выполнились на фактах поездки (context.py).
Нет факта — нет пункта. Объяснение — шаблон с полями фактов, факты пункта уходят во «как узнали».
"""
import json
import re
from functools import lru_cache
from pathlib import Path

from .wish import MONTH_IN, brief

RULES = Path(__file__).resolve().parents[1] / "packing.json"
OPS = {"eq": lambda a, b: a == b, "lt": lambda a, b: a < b, "lte": lambda a, b: a <= b,
       "gt": lambda a, b: a > b, "gte": lambda a, b: a >= b, "in": lambda a, b: a in b,
       "exists": lambda a, b: (a is not None) == b}
FIELD = re.compile(r"\{([a-z_0-9]+(?::[a-z_0-9]+)?)\.([a-z_0-9.$]+)(\|lower)?\}")
KINDS = ("bring", "remind", "skip")


@lru_cache(maxsize=1)
def rules() -> list[dict]:
    return json.loads(RULES.read_text(encoding="utf-8"))["rules"]


def _get(fact: dict, path: str, month: int):
    v = fact.get("value")
    for k in path.replace("$month", str(month)).split("."):
        if not isinstance(v, dict) or k not in v:
            return None
        v = v[k]
    return v


def _check(cond: dict, facts: dict, month: int) -> dict | None:
    """Факт, на котором условие выполнилось, иначе None."""
    f = facts.get(cond["fact"])
    if f is None:
        return None
    v = _get(f, cond["path"], month)
    for op, fn in OPS.items():
        if op in cond:
            want = cond[op]
            if v is None and want is not None and op != "exists":
                return None
            try:
                return f if fn(v, want) else None
            except TypeError:
                return None
    return f if v is not None else None


def _fmt(v):
    return str(round(v)) if isinstance(v, float) else str(v)


def _render(tpl: str, facts: dict, month: int) -> str | None:
    """Шаблон с полями фактов; поле не нашлось или пустое — вариант не подходит."""
    missing = False

    def sub(m):
        nonlocal missing
        f = facts.get(m.group(1))
        v = None if f is None else _get(f, m.group(2), month)
        if v is None and f is not None and "." not in m.group(2):   # text, note у знаний — рядом с value
            v = f.get(m.group(2))
        if v in (None, ""):
            missing = True
            return ""
        s = _fmt(v)
        return s[:1].lower() + s[1:] if m.group(3) else s

    out = FIELD.sub(sub, tpl.replace("{month_in}", MONTH_IN[month]))
    return None if missing else out


def packing(ctx: dict) -> list[dict]:
    facts, month, kids, ages = ctx["facts"], ctx["month"], ctx["kids"], ctx.get("ages") or []
    out, seen = [], set()
    for r in rules():
        if r["id"] in seen or (r.get("mode") == "kids" and not kids) or (r.get("mode") == "adults" and kids):
            continue
        # переноска и кроватка — малышам: подростку коляска не нужна. Возраст не знаем — не отсекаем
        if kids and ages and r.get("ages") and not any(r["ages"][0] <= a <= r["ages"][1] for a in ages):
            continue
        used = [_check(c, facts, month) for c in r["when"]]
        if not all(used):
            continue
        tpls = r["why"] if isinstance(r["why"], list) else [r["why"]]
        why = next((w for w in (_render(t, facts, month) for t in tpls) if w), None)
        if why is None:
            continue
        seen.add(r["id"])
        uniq = list({f["id"]: f for f in used}.values())
        out.append({"id": r["id"], "kind": r["kind"], "icon": r.get("icon", "bag"), "item": r["item"], "why": why,
                    "facts": [brief(f) for f in uniq]})
    return sorted(out, key=lambda x: KINDS.index(x["kind"]))
