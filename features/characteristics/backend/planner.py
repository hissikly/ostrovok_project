"""Планировщик: для пары (отель × характеристика) идёт по плану спеки и решает, где искать дальше.

Шаг → инструмент → если ответ уверенный (≥ min_confidence), стоп; иначе следующий источник.
Слабый ответ запоминаем: если никто не ответит увереннее, факт будет с честной низкой уверенностью.
Никто не ответил → последний шаг «спросить у отеля». Каждое решение пишется в трассу —
её видит гость в карточке («Карта города → не нашли; Ответы отеля → нет; спросили у отеля»).
LLM здесь не участвует: план уже собран и проверен, факты дают только инструменты.
"""
import datetime as dt

from .tools import ABSENT, ASKED, FOUND, NOTHING, TOOLS, UNAVAILABLE, result


def research(hotel: dict, spec: dict, ask: bool = False, asked_before: bool = False) -> dict:
    """{fact | None, trace: [...], state}. ask — можно ли задать вопрос отелю (только прогон по кнопке)."""
    trace, best, accepted = [], None, None
    for step in spec["plan"]:
        tool = TOOLS[step["tool"]]
        if tool.id == "ask_hotelier":
            if accepted:
                break
            if asked_before:
                r = result(ASKED, "Спросили у отеля, ждём ответа")
            elif ask and tool.available():
                r = tool.run(hotel, step["params"], spec, "batch")
            else:
                r = result(NOTHING, "Открытые данные молчат — можно спросить у отеля")
        elif not tool.available():
            r = result(UNAVAILABLE, f"{tool.title}: пока не подключено")
        else:
            r = tool.run(hotel, step["params"], spec)
        trace.append({"tool": tool.id, "title": tool.title, "status": r["status"], "note": r["note"],
                      "confidence": r["confidence"]})
        if r["status"] in (FOUND, ABSENT):
            r["tool"] = tool.id
            if best is None or r["confidence"] > best["confidence"]:
                best = r
            if r["confidence"] >= spec["min_confidence"]:
                accepted = r
                break
    final = accepted or best
    state = "asked" if any(t["status"] == ASKED for t in trace) and not accepted else \
        "answered" if final else "unknown"
    return {"fact": _fact(hotel, spec, final, trace) if final else None, "trace": trace, "state": state}


def characteristic(spec: dict, r: dict | None = None) -> str:
    """near:<id> для «рядом» с карты — тогда факт встаёт в «Что рядом пешком»; остальное — custom:<id>."""
    if spec["kind"] == "near" and spec.get("prefer", "near") == "near" and (r is None or r.get("tool") == "poi_nearby"):
        return f"near:{spec['id']}"
    return f"custom:{spec['id']}"


def _fact(hotel, spec, r, trace):
    today = dt.date.today()
    char = characteristic(spec, r)
    value = dict(r["value"] or {})
    if char.startswith("custom:"):
        value["text"] = text(spec, r)
        if spec["kind"] == "near":
            value.setdefault("answer", (value.get("meters") is None) == (spec.get("prefer") == "far"))
    ev = r["evidence"] or {}
    return {
        "id": f"{hotel['id']}:{char}:hotel", "hotel_id": hotel["id"], "scope": "hotel", "characteristic": char,
        "value": value, "confidence": round(r["confidence"], 2), "source": r["source"],
        "method_version": "agent@0.1",
        "evidence": {**ev, "spec": spec["id"], "agent": [f"{t['title']}: {t['note']}" for t in trace]},
        "obtained_at": ev.get("obtained_at") or today.isoformat(),
        "valid_until": (today + dt.timedelta(days=spec.get("ttl_days", 180))).isoformat(),
        "status": "active",
    }


def text(spec: dict, r: dict) -> str:
    """Одна фраза для карточки: «Стройка в 120 м», «Стройки рядом нет», «Wi-Fi есть»."""
    v = r["value"] or {}
    if r.get("tool") == "poi_nearby":
        kind = v.get("kind") or spec["title"]
        if v.get("meters") is None:
            return spec.get("far_title") or f"{kind}: в {v['within_min']} мин пешком не нашли"
        name = f" «{v['name']}»" if v.get("name") else ""
        dist = f"{v['meters']} м" if v["meters"] < 1000 else f"{v['meters'] / 1000:.1f} км".replace(".", ",")
        return f"{kind}{name} в {dist}, {v['walk_min']} мин пешком"
    if v.get("text"):   # ответ отеля или цитата с сайта — с названием характеристики, чтобы было понятно о чём
        t = v["text"].strip()
        return f"{spec['title']} — {t[:1].lower() + t[1:]}"
    if v.get("answer") is True:
        return spec.get("yes_text") or f"{spec['title']}: да"
    if v.get("answer") is False:
        return spec.get("no_text") or f"{spec['title']}: нет"
    return spec["title"]
