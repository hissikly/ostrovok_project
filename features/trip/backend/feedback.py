"""«Так и было?»: ответы гостей после поездки → факты-наблюдения и сдвиг уверенности исходного факта.

Ответ — «да» / «нет» / «не проверял» по пункту обещания. Ответы по одному факту сводятся в факт
characteristic="guest_feedback", source="guest_feedback", scope="fact:<id исходного факта>"
(через register_provider — его видят карточка и все фичи).

Уверенность исходного факта — байесовски: уверенность расчёта — это априорная доля «так и было»
весом PRIOR ответов; «да» и «нет» гостей добавляются к ней, «не проверял» не считается.
Сдвиг не больше MAX_SHIFT: несколько гостей не перечеркнут расчёт и не сделают его «точным» навсегда.

«Нет» по факту со слов отеля (сайт, ответ отеля) или по пожеланию, которое отель подтвердил, —
вопрос отельеру в очередь Экстранета (features.hotelier.ask_hotel).

Демо: при первом старте подкладываем имитированные ответы (demo=1) по обещаниям трёх демо-отелей;
гость видит, что они демо, в «как узнали».
"""
import datetime as dt
import random
import zlib
from collections import defaultdict

from . import store

PRIOR = 10          # вес уверенности расчёта, в «ответах гостей»
MAX_SHIFT = 0.15
ANSWERS = ("yes", "no", "unsure")
DEMO_HOTELS = ("w201474333", "w51764141", "w711599965")
# доля «так и было» в имитированных ответах — по типам фактов (шум по карте оценить сложнее всего)
DEMO_YES = {"sea_view": 0.93, "sunset_view": 0.9, "beach_route": 0.86, "beach_distance": 0.95, "noise": 0.72}


def shifted(c0: float, yes: int, no: int) -> float:
    c = (c0 * PRIOR + yes) / (PRIOR + yes + no)
    return round(max(c0 - MAX_SHIFT, min(c0 + MAX_SHIFT, c)), 3)


def _aggregate(rows: list[dict]) -> dict[tuple, dict]:
    agg = {}
    for r in rows:
        if r["fact_id"] == "wish":
            continue
        a = agg.setdefault((r["hotel_id"], r["fact_id"]), {"fact_id": r["fact_id"], "characteristic": r["characteristic"],
                                                           "label": r["label"], "yes": 0, "no": 0, "unsure": 0, "demo": 0,
                                                           "confidence_before": r["base_confidence"], "last": r["created_at"]})
        a[r["answer"]] += 1
        a["demo"] += r["demo"]
        a["last"] = max(a["last"], r["created_at"])
    for a in agg.values():
        a["guests"] = a["yes"] + a["no"] + a["unsure"]
        a["confidence"] = shifted(a["confidence_before"], a["yes"], a["no"])
    return agg


def summary(hotel_id: str) -> dict[str, dict]:
    """{id факта: {yes, no, unsure, demo, guests, confidence_before, confidence, label}}."""
    return {fid: a for (_, fid), a in _aggregate(store.feedback_rows(hotel_id)).items()}


def provider() -> list[dict]:
    """Факты-наблюдения guest_feedback для хранилища фактов."""
    out = []
    for (hid, fid), a in _aggregate(store.feedback_rows()).items():
        answered = a["yes"] + a["no"]
        day = a["last"][:10]
        out.append({
            "id": f"{fid}:guest_feedback", "hotel_id": hid, "scope": f"fact:{fid}", "characteristic": "guest_feedback",
            "value": {k: a[k] for k in ("fact_id", "label", "yes", "no", "unsure", "demo", "guests",
                                        "confidence_before", "confidence")},
            # уверенность наблюдения — от числа ответов: 10 ответов ≈ 0,75, 30 и больше — 0,95
            "confidence": round(min(0.95, 0.5 + answered / 40), 2),
            "source": "guest_feedback", "method_version": "trip-feedback@0.1",
            "evidence": {"answers": a["guests"], "demo": a["demo"], "prior_weight": PRIOR, "max_shift": MAX_SHIFT},
            "obtained_at": day, "valid_until": str(dt.date.fromisoformat(day) + dt.timedelta(days=365)), "status": "active",
        })
    return out


def _hotel_said(fact: dict) -> str | None:
    """Тема вопроса отелю, если факт — со слов отеля."""
    src = fact.get("source") or ""
    if src.startswith("web:") or src == "hotelier":
        return fact["characteristic"].split(":", 1)[1] if ":" in fact["characteristic"] else fact["characteristic"]
    return None


def submit(booking: dict, answers: dict[str, str]) -> list[dict]:
    """Ответы гостя по пунктам обещания (и пожеланию, если отель его подтвердил). Возвращает вопросы отелю."""
    from features.hotelier.backend import ask_hotel
    from features.knowledge.backend import topics
    known = {t["id"] for t in topics()}
    hid, now = booking["hotel_id"], store.now()
    rows, asked = [], []
    for it in booking["promise"]:
        a = answers.get(it["id"])
        if a not in ANSWERS:
            continue
        f = it["facts"][0]
        rows.append({"booking_id": booking["id"], "hotel_id": hid, "fact_id": it["id"], "characteristic": f["characteristic"],
                     "label": it["title"], "answer": a, "base_confidence": f["confidence"], "demo": 0, "created_at": now})
        topic = _hotel_said(f)
        if a == "no" and topic:
            asked.append(ask_hotel(hid, topic if topic in known else None,
                                   f"Гость после поездки: «{it['title']}» — не так. Что изменилось"))
    a = answers.get("wish")
    if a in ANSWERS and booking.get("status") == "confirmed":
        rows.append({"booking_id": booking["id"], "hotel_id": hid, "fact_id": "wish", "characteristic": "booking_wish",
                     "label": booking["wish"]["text"], "answer": a, "base_confidence": 0.9, "demo": 0, "created_at": now})
        if a == "no":
            asked.append(ask_hotel(hid, None, f"Гость после поездки: номер был не по пожеланию «{booking['wish']['text']}». Что случилось"))
    store.add_feedback(rows)
    return asked


def seed_demo() -> None:
    """Имитированные ответы гостей для показа: 6–12 на пункт обещания демо-отелей (окна на запад, верхний этаж, май)."""
    if store.has_demo():
        return
    from .promise import promise
    rows = []
    day0 = dt.date(2026, 9, 1)
    for hid in DEMO_HOTELS:
        for it in promise(hid, 5, "W", None) or []:
            f = it["facts"][0]
            rnd = random.Random(zlib.crc32(it["id"].encode()))
            n = rnd.randint(6, 12)
            p = DEMO_YES.get(f["characteristic"], 0.8)
            for i in range(n):
                x = rnd.random()
                a = "yes" if x < p else "unsure" if x < p + (1 - p) / 3 else "no"
                rows.append({"booking_id": None, "hotel_id": hid, "fact_id": it["id"], "characteristic": f["characteristic"],
                             "label": it["title"], "answer": a, "base_confidence": f["confidence"], "demo": 1,
                             "created_at": f"{day0 + dt.timedelta(days=rnd.randint(0, 50))}T12:00:00"})
    store.add_feedback(rows)


def stats() -> dict:
    """Метрика калибровки: доля «так и было» среди ответивших «да»/«нет» — по типам фактов."""
    by = defaultdict(lambda: {"yes": 0, "no": 0, "unsure": 0, "demo": 0})
    for r in store.feedback_rows():
        b = by[r["characteristic"]]
        b[r["answer"]] += 1
        b["demo"] += r["demo"]
    out = {}
    for ch, b in sorted(by.items()):
        n = b["yes"] + b["no"]
        out[ch] = {**b, "share_yes": round(b["yes"] / n, 2) if n else None}
    return out
