"""Бронь целиком: пожелание, обещание, чемодан, ответ отеля, ответы гостя «Так и было?»."""
from features.facts.backend import refresh

from . import store
from .context import context
from .feedback import submit, summary
from .packing import packing
from .promise import items as promise_items
from .wish import items as wish_items, text as wish_text

STATUS = {"sent": "Ждём ответа отеля", "confirmed": "Отель подтвердил", "declined": "Отель предложил другое"}


def _hotel(h: dict) -> dict:
    return {"id": h["id"], "name": h["name"], "address": h.get("address"), "lat": h["lat"], "lon": h["lon"],
            "price_rub": h["mock"]["price_rub"], "rating": h["mock"]["rating"], "reviews": h["mock"]["reviews"]}


def book(hotel_id: str, month: int, facade: str | None, floor: int | None, drop: set[str]) -> dict | None:
    ctx = context(hotel_id, month, facade, floor)
    if ctx is None:
        return None
    its = [x for x in wish_items(ctx) if x["id"] not in drop]
    floor_item = next((x for x in its if x["id"] == "floor"), None)
    w = {"text": wish_text(its), "items": its, "min_floor": floor_item["min_floor"] if floor_item else None}
    seen, prom = set(), []
    for it in promise_items(ctx):
        if it["id"] not in seen:
            seen.add(it["id"])
            prom.append(it)
    return store.create_booking(hotel_id, month, ctx["side"], ctx["floor"], w, prom)


def _short(b: dict) -> dict:
    return {k: b[k] for k in ("id", "hotel_id", "month", "facade", "floor", "wish", "status", "hotel_reply",
                              "replied_at", "finished_at", "created_at")} | {"status_text": STATUS[b["status"]]}


def trip(bid: str, kids: bool = False) -> dict | None:
    b = store.get_booking(bid)
    if b is None:
        return None
    ctx = context(b["hotel_id"], b["month"], b["facade"], b["floor"], kids)
    summ = summary(b["hotel_id"])
    mine = {r["fact_id"]: r["answer"] for r in store.feedback_rows(booking_id=bid)}
    prom = [{**it, "guests": summ.get(it["id"])} for it in b["promise"]]
    return {**_short(b), "hotel": _hotel(ctx["hotel"]), "kids": kids, "promise": prom,
            "packing": packing(ctx), "answers": mine}


def list_bookings(hotel_id: str | None = None) -> list[dict]:
    return [_short(b) for b in store.bookings(hotel_id)]


def hotel_reply(hotel_id: str, bid: str, answer: str, text: str) -> dict | None:
    b = store.get_booking(bid)
    if b is None or b["hotel_id"] != hotel_id:
        return None
    if answer == "confirm":
        return _short(store.reply(bid, "confirmed", text.strip() or "Подтверждаем, номер подберём по пожеланию"))
    return _short(store.reply(bid, "declined", text.strip() or "Не сможем выполнить пожелание полностью"))


def finish(bid: str, answers: dict[str, str] | None = None) -> dict | None:
    b = store.get_booking(bid)
    if b is None:
        return None
    if not b["finished_at"]:
        store.finish(bid)
    if answers:
        done = {r["fact_id"] for r in store.feedback_rows(booking_id=bid)}
        submit(store.get_booking(bid), {k: v for k, v in answers.items() if k not in done})
        refresh()   # уверенность фактов и «N гостей подтвердили» — сразу в карточке
    return {"ok": True}
