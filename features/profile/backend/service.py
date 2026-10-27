"""Профиль гостя: его поездки, «Так и было?» по обещанию и по фильтрам поиска, отзыв об отеле.

Гость в демо один (входа нет): профиль — все брони сервиса (features/trip) плюс две прошлые демо-поездки.
Вопросы после поездки:
  · по обещанию и пожеланию — те же, что в «Моей поездке», ответы уходят в features/trip
    (сдвигают уверенность фактов, «нет» со слов отеля — вопрос отельеру);
  · по фильтрам, с которыми гость выбрал отель, — если обещание их ещё не спросило:
    «Вы искали „Аптека рядом“. Мы считали: аптека в 237 м, 5 мин пешком — так и было?».
    Фильтр, по которому отель не подходил, не спрашиваем; «не знали» — спрашиваем: ответ гостя и есть новые данные.
"""
import logging

from features.facts.backend import facts_for
from features.trip.backend import backdate, book, finish, hotel_reply, list_bookings, trip

from . import store

log = logging.getLogger(__name__)
ANSWERS = ("yes", "no", "unsure")
MONTH = ["", "январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"]
# какие характеристики проверяет фильтр — если они уже в обещании, второй раз не спрашиваем
LENS_CHARS = {"sea_view": {"sea_view"}, "sunset": {"sunset_view"}, "beach_near": {"beach_route", "beach_distance"},
              "flat": {"beach_route"}, "quiet": {"noise"}}


def _lenses():
    from features.search.backend.lenses import BY_ID   # лениво: каталог фильтров тянет nearby и sights
    return BY_ID


def questions(t: dict) -> list[dict]:
    """Вопросы «Так и было?» по поездке: обещание, пожелание (если отель подтвердил), фильтры поиска."""
    qs = [{"id": p["id"], "kind": "promise", "icon": p.get("icon"), "title": p["title"], "note": p.get("note"),
           "answer": t["answers"].get(p["id"])} for p in t["promise"]]
    if t["status"] == "confirmed" and t["wish"]["items"]:
        qs.append({"id": "wish", "kind": "wish", "icon": "window", "title": "Номер по пожеланию",
                   "note": t["wish"]["text"], "answer": t["answers"].get("wish")})
    covered = {p["facts"][0]["characteristic"] for p in t["promise"] if p.get("facts")}
    mine = {r["lens"]: r["answer"] for r in store.lens_answers(t["id"])}
    by_id, facts = _lenses(), None
    for lid in t.get("lenses") or []:
        lens = by_id.get(lid)
        if lens is None or LENS_CHARS.get(lid, set()) & covered:
            continue
        facts = facts if facts is not None else facts_for(t["hotel_id"])
        r = lens["fn"](facts, {"month": t["month"]})
        if r["state"] == "no":
            continue
        qs.append({"id": f"lens:{lid}", "kind": "lens", "icon": lens.get("icon"), "title": lens["title"],
                   "note": "Мы не знали точно — расскажите, как было" if r["state"] == "unknown" else f"Мы считали: {r['text'][:1].lower()}{r['text'][1:]}",
                   "claim": r["state"], "answer": mine.get(lid)})
    return qs


def _card(t: dict) -> dict:
    qs, by_id = questions(t), _lenses()
    past = bool(t["finished_at"])
    return {"id": t["id"], "hotel": t["hotel"], "month": t["month"], "facade": t["facade"], "floor": t["floor"],
            "guests": t["guests"], "wish": t["wish"]["text"], "status": t["status"], "status_text": t["status_text"],
            "past": past, "when": f"{MONTH[t['month']].capitalize()} {t['finished_at'][:4]}" if past else None,
            "lenses": [{"id": i, "title": by_id[i]["title"], "icon": by_id[i].get("icon")} for i in t.get("lenses") or [] if i in by_id],
            "questions": qs, "answered": sum(bool(q["answer"]) for q in qs),
            "review": store.review(t["id"]), "created_at": t["created_at"], "finished_at": t["finished_at"]}


def profile() -> dict:
    """Все поездки: сначала предстоящие (новые сверху), потом прошлые (последние сверху)."""
    cards = [_card(t) for b in list_bookings() if (t := trip(b["id"]))]
    up = sorted((c for c in cards if not c["past"]), key=lambda c: c["created_at"], reverse=True)
    past = sorted((c for c in cards if c["past"]), key=lambda c: c["finished_at"], reverse=True)
    return {"trips": up + past,
            "summary": {"trips": len(cards), "past": len(past), "answers": sum(c["answered"] for c in cards),
                        "reviews": sum(c["review"] is not None for c in cards),
                        # прошлые поездки, где остались вопросы без ответа, — точка у «Профиля» в шапке
                        "pending": sum(c["answered"] < len(c["questions"]) for c in past)}}


def card(bid: str) -> dict | None:
    t = trip(bid)
    return _card(t) if t else None


def answer(bid: str, answers: dict[str, str]) -> dict | None:
    """Ответы «Так и было?»: по обещанию и пожеланию — в features/trip, по фильтрам — сюда. Отмечает «Поездка завершена»."""
    t = trip(bid)
    if t is None:
        return None
    answers = {k: v for k, v in answers.items() if v in ANSWERS}
    lens_q = {q["id"]: q for q in questions(t) if q["kind"] == "lens"}
    for k, v in answers.items():
        if k in lens_q:
            q = lens_q[k]
            store.add_lens_answer(bid, t["hotel_id"], k.split(":", 1)[1], q["title"], q["claim"], v)
    finish(bid, {k: v for k, v in answers.items() if not k.startswith("lens:")})
    return card(bid)


def save_review(bid: str, stars: int, text: str) -> dict | None:
    t = trip(bid)
    if t is None:
        return None
    store.save_review(bid, t["hotel_id"], stars, " ".join(text.split())[:1000])
    return card(bid)


def stats() -> dict:
    """Метрика: совпал ли отель с фильтром, по которому его выбрали, — доля «так и было» среди «да»/«нет»."""
    by = {}
    for r in store.lens_answers():
        b = by.setdefault(r["lens"], {"title": r["title"], "yes": 0, "no": 0, "unsure": 0})
        b[r["answer"]] += 1
    for b in by.values():
        n = b["yes"] + b["no"]
        b["share_yes"] = round(b["yes"] / n, 2) if n else None
    return by


def _guests_word(g: dict | None) -> str:
    g = g or {"adults": 2, "children": []}
    a, k = g.get("adults", 2), len(g.get("children") or [])
    who = "Один" if a == 1 and not k else "Пара" if a == 2 and not k else "Семья с детьми" if k else "Компания"
    return who


def hotel_reviews(hotel_id: str) -> dict:
    """Отзывы гостей после поездки: звёзды, текст и что из обещанного подтвердили / не подтвердили.
    Для карточки отеля и Экстранета; демо-отзывы помечены."""
    items, miss = [], {}
    for r in store.hotel_reviews(hotel_id):
        if r["booking_id"].startswith("demo:"):
            x = r["extra"] or {}
            when, guest, yes, no = x.get("when"), x.get("guest", "Гость"), x.get("yes", []), x.get("no", [])
        else:
            t = trip(r["booking_id"])
            if t is None:
                continue
            qs = questions(t)
            when = f"{MONTH[t['month']].capitalize()} {(t['finished_at'] or t['created_at'])[:4]}"
            guest = _guests_word(t["guests"])
            yes = [q["title"] for q in qs if q["answer"] == "yes"]
            no = [q["title"] for q in qs if q["answer"] == "no"]
        for title in no:
            miss[title] = miss.get(title, 0) + 1
        items.append({"id": r["booking_id"], "stars": r["stars"], "text": r["text"], "when": when, "guest": guest,
                      "yes": yes, "no": no, "demo": bool(r["demo"]), "created_at": r["created_at"]})
    n = len(items)
    return {"count": n, "avg": round(sum(i["stars"] for i in items) / n, 1) if n else None,
            "demo": sum(i["demo"] for i in items), "items": items,
            # что гости чаще всего не подтвердили — отелю, чтобы поправить описание или номер
            "mismatches": [{"title": k, "count": v} for k, v in sorted(miss.items(), key=lambda kv: -kv[1])]}


# Демо-отзывы о двух главных отелях демо (Pullman, Azimut) — без брони, помечены «демо»
DEMO_REVIEWS = [
    ("w201474333", 5, "2026-07-14T10:00:00", {"when": "Июль 2026", "guest": "Пара",
     "yes": ["Море из окна", "Закат над морем из окна", "На пляж 8 минут пешком"], "no": []},
     "Брали запад и верхний этаж, как советовали, — закат каждый вечер прямо в окне. К морю вниз быстро, обратно в горку, но терпимо."),
    ("w201474333", 4, "2026-06-02T10:00:00", {"when": "Май 2026", "guest": "Семья с детьми",
     "yes": ["Море из окна", "На пляж 8 минут пешком"], "no": ["Ночью спокойно"]},
     "Море из окна правда видно. Но в выходные под окнами шумно до полуночи — с маленьким ребёнком лучше просить номер повыше."),
    ("w201474333", 5, "2025-09-20T10:00:00", {"when": "Сентябрь 2025", "guest": "Один",
     "yes": ["Море из окна", "Закат над морем из окна", "Ночью спокойно"], "no": []},
     "Всё как в описании. Удобно, что заранее знал про подъём от пляжа."),
    ("w51764141", 4, "2026-08-11T10:00:00", {"when": "Август 2026", "guest": "Пара",
     "yes": ["Море из окна", "Завтрак за доплату, шведский стол"], "no": ["Закат над морем из окна"]},
     "Завтраки отличные, хоть и за доплату, море видно. Закат из нашего номера закрывал соседний корпус — уточняйте сторону."),
    ("w51764141", 5, "2025-07-03T10:00:00", {"when": "Июнь 2025", "guest": "Компания",
     "yes": ["Море из окна", "Ночью спокойно"], "no": []},
     "Тихо, чисто, до набережной пешком. Вернёмся."),
]


def seed_demo_reviews() -> None:
    if store.has_demo_reviews():
        return
    for i, (hid, stars, at, extra, text) in enumerate(DEMO_REVIEWS, 1):
        store.save_review(f"demo:{hid}:{i}", hid, stars, text, demo=True, extra=extra, created_at=at)


# Две прошлые поездки демо-гостя: одна с ответами и отзывом, другую ещё не оценили — профиль не пустой с первого запуска
DEMO = [
    {"hotel_id": "w52526314", "month": 8, "created_at": "2025-07-02T21:14:00", "finished_at": "2025-08-17T12:00:00",
     "lenses": ["sea_view", "quiet", "near_pharmacy", "near_park"],
     "answers": {"*": "yes", "lens:near_park": "unsure"},
     "review": (4, "Ночью правда тихо, море из окна только краешком — как и предупреждали. "
                   "До пляжа далеко и обратно в гору, зато аптека и парк в пяти минутах.")},
    {"hotel_id": "w147645155", "month": 9, "created_at": "2026-08-20T19:05:00", "finished_at": "2026-09-21T12:00:00",
     "lenses": ["sunset", "beach_near", "near_cafe"], "answers": None, "review": None},
]


def seed_demo() -> None:
    if store.demo_bookings() & {b["id"] for b in list_bookings()}:
        return
    for d in DEMO:
        b = book(d["hotel_id"], d["month"], None, None, set(), {"adults": 2, "children": []}, [], d["lenses"])
        if b is None:
            log.warning("profile: демо-поездка не создана, нет отеля %s", d["hotel_id"])
            continue
        store.mark_demo(b["id"])
        hotel_reply(d["hotel_id"], b["id"], "confirm", "")
        backdate(b["id"], d["created_at"], d["finished_at"])
        if d["answers"]:
            t = trip(b["id"])
            qs = questions(t)
            answer(b["id"], {q["id"]: d["answers"].get(q["id"], d["answers"]["*"]) for q in qs})
            store.save_review(b["id"], d["hotel_id"], *d["review"], demo=True)
