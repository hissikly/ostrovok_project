"""Сравнение ответа отеля с тем, что система посчитала сама.

Возвращает описание расхождения или None. Правила на темы базы знаний (features/knowledge/topics.json),
работают без LLM: ответ отеля разбираем регулярками, расчёт берём уже готовым (value из knowledge.answers).
"""
import re

ALL_ROOMS = re.compile(r"(из|во|в)\s+(всех|каждого|любого)\s+(номер|окн|комнат)|все\s+номера|из\s+любого\s+окна", re.I)
NO_VIEW = re.compile(r"(нет|без)\s+(вида|видa)|моря?\s+не\s+видно|не\s+видно\s+моря", re.I)
FROM_FLOOR = re.compile(r"с\s+(\d{1,2})\s*-?\s*(?:го|ого|ого)?\s+этаж", re.I)
NUMBER = re.compile(r"(\d+(?:[.,]\d+)?)")
SIDE_GEN = {"N": "севера", "E": "востока", "S": "юга", "W": "запада"}
SIDE_ACC = {"N": "север", "E": "восток", "S": "юг", "W": "запад"}


def _num(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _sea_view(hotel_text: str, hotel_value: dict, computed: dict):
    sides = (computed.get("value") or {}).get("sides") or {}
    if not sides:
        return None
    seen = {s: fl for s, fl in sides.items() if fl}
    if ALL_ROOMS.search(hotel_text) or (hotel_value or {}).get("rooms") == "все номера":
        blind = [s for s, fl in sides.items() if not fl]
        high = {s: fl for s, fl in seen.items() if fl > 1}
        if blind:
            return f"По расчёту из окон на {' и '.join(SIDE_ACC[s] for s in blind)} моря почти не видно"
        if high:
            s, fl = min(high.items(), key=lambda x: x[1])
            return f"По расчёту с {SIDE_GEN[s]} море видно только с {fl}-го этажа"
    elif NO_VIEW.search(hotel_text) and seen:
        s, fl = min(seen.items(), key=lambda x: x[1])
        return f"По расчёту с {SIDE_GEN[s]} море видно с {fl}-го этажа"
    else:
        m = FROM_FLOOR.search(hotel_text)
        if m and seen and abs(int(m.group(1)) - min(seen.values())) >= 3:
            return f"По расчёту море видно с {min(seen.values())}-го этажа, а не с {m.group(1)}-го"
    return None


def _beach(hotel_text: str, hotel_value: dict, computed: dict):
    said = _num((hotel_value or {}).get("minutes"))
    if said is None:
        m = re.search(r"(\d+)\s*(мин|минут)", hotel_text, re.I)
        said = float(m.group(1)) if m else None
    v = computed.get("value") or {}
    calc = _num(v.get("minutes") or v.get("walk_min"))
    if said is None or calc is None:
        return None
    if calc - said >= 5 and calc >= 1.8 * said:
        back = v.get("back_minutes")
        climb = v.get("climb_back_m") or 0
        tail = f", обратно {back} мин в гору на {climb} м" if back and climb >= 10 else ""
        return f"По пешему маршруту до пляжа {int(calc)} мин{tail}"
    if said - calc >= 10 and said >= 1.8 * calc:
        return f"По пешему маршруту до пляжа всего {int(calc)} мин"
    return None


def _floors(hotel_text: str, hotel_value: dict, computed: dict):
    said = _num((hotel_value or {}).get("floors"))
    if said is None:
        m = NUMBER.search(hotel_text)
        said = _num(m.group(1)) if m else None
    calc = _num((computed.get("value") or {}).get("floors"))
    if said and calc and abs(said - calc) >= 2:
        return f"На открытой карте у корпуса {int(calc)} этажей"
    return None


RULES = {"sea_view": _sea_view, "beach": _beach, "floors": _floors}


def check(topic: str, hotel_answer: dict, computed: dict | None) -> dict | None:
    """hotel_answer — запись базы знаний отеля, computed — ответ, посчитанный системой."""
    rule = RULES.get(topic)
    if not rule or not computed:
        return None
    if (hotel_answer.get("evidence") or {}).get("action") == "adopted_computed":
        return None   # отель принял расчёт: в value может остаться прежнее «все номера» / «5 минут»
    reason = rule(hotel_answer.get("text") or "", hotel_answer.get("value") or {}, computed)
    if not reason:
        return None
    return {"topic": topic, "hotel_text": hotel_answer.get("text"), "computed_text": computed.get("text"),
            "computed_source": computed.get("source"), "computed_confidence": computed.get("confidence"),
            "reason": reason}


# --- сайт отеля ↔ расчёт ------------------------------------------------------------------------
# Что отель обещает на своём сайте (features/web_sources: web:sea_view, web:beach_claim) сверяем
# теми же правилами, что и ответ отеля. Сайт — тоже голос отеля, но не ответ на наш вопрос:
# гость видит «Отель пишет иначе», отельер в Экстранете — цитату со своего сайта и расчёт.
SITE_TOPIC = {"sea_view": "sea_view", "beach": "beach_claim"}
FIRST_LINE_M = 350           # «первая линия», а до воды по прямой дальше — расхождение
WALK_M_PER_MIN = 80          # «500 м до моря» → ~6 мин пешком (4,8 км/ч)


def _site_beach_meters(v: dict, straight_m: float | None, computed: dict):
    """«В 200 м от моря» / «первая линия» сверяем с расстоянием по прямой, а не с пешим маршрутом."""
    if not straight_m:
        return None
    route = (computed.get("value") or {}).get("minutes")
    tail = f", пешком {int(route)} мин" if route else ""
    said = v.get("meters")
    if said and straight_m - said >= 250 and straight_m >= 1.5 * said:
        return f"По карте до моря {int(straight_m)} м по прямой{tail}"
    if not said and v.get("first_line") and straight_m > FIRST_LINE_M:
        return f"По карте до моря {int(straight_m)} м по прямой{tail} — это не первая линия"
    return None


def check_site(topic: str, site: dict | None, computed: dict | None, straight_m: float | None = None) -> dict | None:
    """site — ответ с сайта отеля (web_sources.answer: text, value, quote, url, source);
    straight_m — до моря по прямой (факт beach_distance) для заявлений в метрах."""
    if not site or not computed or topic not in SITE_TOPIC:
        return None
    v = site.get("value") or {}
    if topic == "beach":
        reason = (_beach(site.get("quote") or "", {"minutes": v["walk_min"]}, computed) if v.get("walk_min")
                  else _site_beach_meters(v, straight_m, computed))
    else:
        reason = RULES[topic](site.get("quote") or "", v, computed)
        # «есть номера с видом на море», а по расчёту моря не видно ни с одной стороны
        if not reason and v.get("rooms") and computed.get("text") == "Моря из окон не видно":
            reason = "По расчёту моря из окон не видно ни с одной стороны"
    if not reason:
        return None
    return {"topic": topic, "kind": "site", "hotel_text": site.get("quote"), "hotel_value": v,
            "site_url": site.get("url"), "site_source": site.get("source"),
            "computed_text": computed.get("text"), "computed_source": computed.get("source"),
            "computed_confidence": computed.get("confidence"), "reason": reason}
