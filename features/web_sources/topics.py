"""Темы, которые ищем на сайтах отелей: вопрос, слова для поиска, поля ответа и фраза для гостя.

id совпадает с темой базы знаний (features/knowledge/topics.json), если такая есть, — тогда ответ
с сайта встаёт в «Частые вопросы». Остальные (бассейн, кухня, свой пляж…) — строки «Что важно знать».
sea_view и beach_claim — что отель обещает сам; их сверяет с расчётом features/conflicts.
"""


def _yes(v, key, yes, no="", extra=None):
    if v.get(key) == "нет":
        return no
    return yes + (extra(v) if extra else "")


def _pets(v):
    if v.get("dogs") == "нет":
        return "С питомцами нельзя"
    t = "Можно с питомцем"
    if v.get("max_kg"):
        t += f" до {v['max_kg']} кг"
    if v.get("fee_rub"):
        t += f", доплата {v['fee_rub']} ₽"
    return t


def _checkin(v):
    parts = []
    if v.get("checkin"):
        parts.append(f"заезд с {v['checkin']}")
    if v.get("checkout"):
        parts.append(f"выезд до {v['checkout']}")
    return (", ".join(parts) or "Время заезда указано на сайте").capitalize()


def _price(v):
    p = v.get("price_rub")
    return "" if p is None else ", бесплатно" if p == 0 else f", {p} ₽"


def _breakfast(v):
    t = "Завтрак включён" if v.get("breakfast") == "включён" else "Завтрак за доплату" if v.get("breakfast") == "за доплату" \
        else "Нет завтрака" if v.get("breakfast") == "нет" else "Есть завтрак"
    return t + (f", {v['kind']}" if v.get("kind") else "")


def _crib(v):
    c = v.get("crib")
    if c == "нет":
        return "Детской кроватки нет"
    t = "Детская кроватка бесплатно" if c == "бесплатно" else "Детская кроватка за доплату" if c == "за доплату" else "Есть детская кроватка"
    return t + (", по запросу заранее" if v.get("preorder") == "нужно" else "")


def _rooms(word):
    def f(v):
        key = next(iter(v))
        w = v.get(key)
        if w == "нет":
            return f"{word} нет"
        return f"{word} во всех номерах" if w == "во всех номерах" else f"{word} в части номеров" if w == "в части номеров" else f"Есть {word.lower()}"
    return f


def _transfer(v):
    t = v.get("transfer")
    if t == "нет":
        return "Трансфера нет"
    src = "с вокзала" if v.get("from") == "вокзал" else "из аэропорта"
    return ("Бесплатный трансфер " if t == "бесплатно" else "Трансфер за доплату " if t == "за доплату"
            else "Есть трансфер ") + src + (f", {v['price_rub']} ₽" if v.get("price_rub") else "")


def _noise_rules(v):
    t = f"Тишина с {v['quiet_from']}"
    return t + (", вечеринки нельзя" if v.get("parties") == "нельзя" else "")


def _sea_view(v):
    return "Вид на море из всех номеров" if v.get("rooms") == "все номера" else "Есть номера с видом на море"


def _beach_claim(v):
    if v.get("walk_min"):
        return f"До моря {v['walk_min']} мин"
    if v.get("meters"):
        return f"До моря {v['meters']} м"
    return "Первая линия у моря"


def _pool(v):
    t = {"крытый": "Крытый бассейн", "открытый": "Открытый бассейн"}.get(v.get("kind"), "Есть бассейн")
    return t + (" с подогревом" if v.get("heated") else "")


TOPICS = [
    {"id": "pets", "question": "Можно с питомцем?", "query": "проживание с животными питомцы собаки кг доплата",
     "fields": [{"id": "dogs", "type": "choice", "options": ["да", "нет"]}, {"id": "cats", "type": "choice", "options": ["да", "нет"]},
                {"id": "max_kg", "type": "number"}, {"id": "fee_rub", "type": "number"}], "text": _pets},
    {"id": "checkin", "question": "Во сколько заезд и выезд?", "query": "заезд выезд расчетный час заселение время",
     "fields": [{"id": "checkin", "type": "time ЧЧ:ММ"}, {"id": "checkout", "type": "time ЧЧ:ММ"}], "text": _checkin},
    {"id": "parking", "question": "Есть ли парковка у отеля?", "query": "парковка паркинг стоянка автомобиль",
     "fields": [{"id": "parking", "type": "choice", "options": ["есть", "нет"]}, {"id": "price_rub", "type": "number, 0 если бесплатно"}],
     "text": lambda v: "Парковки нет" if v.get("parking") == "нет" else "Есть парковка" + _price(v)},
    {"id": "breakfast", "question": "Есть ли завтрак?", "query": "завтрак шведский стол питание ресторан",
     "fields": [{"id": "breakfast", "type": "choice", "options": ["включён", "за доплату", "есть", "нет"]},
                {"id": "kind", "type": "choice", "options": ["шведский стол", "меню"]}], "text": _breakfast},
    {"id": "crib", "question": "Есть ли детская кроватка?", "query": "детская кроватка манеж ребенок малыш",
     "fields": [{"id": "crib", "type": "choice", "options": ["бесплатно", "за доплату", "есть", "нет"]},
                {"id": "preorder", "type": "choice", "options": ["нужно", "не нужно"]}], "text": _crib},
    {"id": "ac", "question": "Есть ли кондиционер?", "query": "кондиционер сплит-система номер",
     "fields": [{"id": "ac", "type": "choice", "options": ["во всех номерах", "в части номеров", "есть", "нет"]}], "text": _rooms("Кондиционер")},
    {"id": "balcony", "question": "Есть ли балкон?", "query": "балкон лоджия терраса номер",
     "fields": [{"id": "balcony", "type": "choice", "options": ["во всех номерах", "в части номеров", "нет"]}], "text": _rooms("Балкон")},
    {"id": "transfer", "question": "Есть ли трансфер из аэропорта?", "query": "трансфер аэропорт вокзал встреча",
     "fields": [{"id": "transfer", "type": "choice", "options": ["бесплатно", "за доплату", "есть", "нет"]}, {"id": "price_rub", "type": "number"}],
     "text": _transfer},
    {"id": "noise_rules", "question": "Можно ли шуметь и праздновать?", "query": "тишина правила проживания шум вечеринки",
     "fields": [{"id": "quiet_from", "type": "time ЧЧ:ММ"}, {"id": "parties", "type": "choice", "options": ["можно", "нельзя"]}],
     "text": _noise_rules},
    {"id": "quiet_rooms", "icon": "mute", "synonyms": ["шумоизоляция", "звукоизоляция", "тонкие стены", "слышно соседей"], "question": "Хорошая ли шумоизоляция?", "query": "шумоизоляция звукоизоляция окна стеклопакеты тихо",
     "fields": [{"id": "noise", "type": "choice", "options": ["не слышно", "шумоизоляция"]}],
     "text": lambda v: "Хорошая шумоизоляция в номерах"},
    {"id": "sea_view", "question": "Есть ли номера с видом на море?", "query": "вид на море номер панорамный",
     "fields": [{"id": "rooms", "type": "choice", "options": ["все номера", "часть номеров"]}], "text": _sea_view},
    {"id": "beach_claim", "question": "Сколько до моря, по словам отеля?", "query": "минут до моря пляж метров первая линия",
     "fields": [{"id": "walk_min", "type": "number"}, {"id": "meters", "type": "number"}], "text": _beach_claim},
    {"id": "own_beach", "icon": "beach", "synonyms": ["свой пляж", "собственный пляж", "пляж отеля", "частный пляж", "лежаки", "шезлонги"], "question": "Есть ли свой пляж?", "query": "собственный пляж оборудованный шезлонги",
     "fields": [{"id": "own_beach", "icon": "beach", "synonyms": ["свой пляж", "собственный пляж", "пляж отеля", "частный пляж", "лежаки", "шезлонги"], "type": "choice", "options": ["есть", "нет"]}],
     "text": lambda v: "Нет своего пляжа" if v.get("own_beach") == "нет" else "Есть свой пляж"},
    {"id": "pool", "icon": "waves", "synonyms": ["бассейн", "поплавать", "подогрев бассейна", "крытый бассейн", "открытый бассейн"], "question": "Есть ли бассейн?", "query": "бассейн подогрев открытый крытый",
     "fields": [{"id": "pool", "icon": "waves", "synonyms": ["бассейн", "поплавать", "подогрев бассейна", "крытый бассейн", "открытый бассейн"], "type": "choice", "options": ["есть", "нет"]}, {"id": "kind", "type": "choice", "options": ["открытый", "крытый"]},
                {"id": "heated", "type": "bool"}], "text": _pool},
    {"id": "kitchen", "icon": "fork", "synonyms": ["кухня", "кухонька", "плита", "готовить", "приготовить еду", "посуда"], "question": "Есть ли кухня в номере?", "query": "кухня мини-кухня апартаменты плита",
     "fields": [{"id": "kitchen", "icon": "fork", "synonyms": ["кухня", "кухонька", "плита", "готовить", "приготовить еду", "посуда"], "type": "choice", "options": ["во всех номерах", "в части номеров", "нет"]}], "text": _rooms("Кухня")},
    {"id": "wifi", "icon": "bolt", "synonyms": ["wi-fi", "wifi", "вайфай", "вай-фай", "интернет", "вай фай"], "question": "Есть ли Wi-Fi?", "query": "wi-fi интернет вайфай бесплатный",
     "fields": [{"id": "wifi", "icon": "bolt", "synonyms": ["wi-fi", "wifi", "вайфай", "вай-фай", "интернет", "вай фай"], "type": "choice", "options": ["бесплатно", "есть", "нет"]}],
     "text": lambda v: "Wi-Fi нет" if v.get("wifi") == "нет" else "Бесплатный Wi-Fi" if v.get("wifi") == "бесплатно" else "Есть Wi-Fi"},
    {"id": "lift", "icon": "building", "synonyms": ["лифт", "подъемник"], "question": "Есть ли лифт?", "query": "лифт этаж подъем",
     "fields": [{"id": "lift", "icon": "building", "synonyms": ["лифт", "подъемник"], "type": "choice", "options": ["есть", "нет"]}],
     "text": lambda v: "Лифта нет" if v.get("lift") == "нет" else "Есть лифт"},
]
