"""Разбор свободного ответа отельера по полям темы — без LLM.

Идея как у моделей-«выбиралок»: на каждое поле — вопрос с готовыми вариантами, а не сочинение текста.
1. Режем ответ на части по точкам и запятым, для поля ищем часть про него (подсказка kw из topics.json).
2. choice: отрицание в этой части → «нет»; «бесплатно» / «за доплату» по словам и суммам; варианты match — по своим словам.
3. number / time: число рядом с единицей (кг, ₽, мин, этаж) или время «с 14», «14:00».
Ничего не нашли — поле «не сказано». Последнее слово за отельером: он видит «как мы поняли» и подтверждает.
"""
import re

NEG = re.compile(r"(?<![а-яё])(нет|нельзя|без|невозмож\w*|не получится|запрещ\w*|отсутств\w*|не (пуска|бер|бер[её]м|принима|разреш|предоставл|допуска|работа|можем|положен)\w*)(?![а-яё])")
FREE = re.compile(r"бесплат|в подарок|входит в стоимость|включ[её]н|в цене")
PAID = re.compile(r"доплат|(?<!бес)платн|за деньги|отдельно|\d+\s*(р(?![а-яё])|руб|₽)|тысяч")
WORD_NUM = {"тысяч": 1000, "полтысяч": 500, "пятьсот": 500, "триста": 300, "двести": 200, "сто": 100,
            "десять": 10, "пять": 5, "пятнадцать": 15, "двадцать": 20, "тридцать": 30}


def _parts(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"[.;!?\n]+|,(?!\d)", text.lower().replace("ё", "е")) if p.strip()]


def _about(parts, kw):
    if not kw:
        return []
    rx = re.compile(kw)
    return [p for p in parts if rx.search(p)]


def _choice(f, parts, whole):
    opts = f["options"]
    if "match" in f:
        where = " ".join(_about(parts, f.get("kw"))) or whole
        for opt, rx in f["match"].items():
            if re.search(rx, where):
                return opt
        return None
    about = _about(parts, f.get("kw"))
    if not about:
        return None
    clause = " ".join(about)
    neg = "нет" if "нет" in opts else None
    if neg and NEG.search(clause):
        return neg
    if "бесплатно" in opts and FREE.search(clause) and not PAID.search(clause):
        return "бесплатно"
    if "за доплату" in opts and PAID.search(clause):
        return "за доплату"
    if "включён" in opts and FREE.search(clause):
        return "включён"
    # тема упомянута без отрицания — значит «да / есть / включено»
    positive = [o for o in opts if o in ("да", "есть", "включён", "во всех номерах", "нужно", "бесплатно")]
    return positive[0] if positive else None


def _money(s):
    m = re.search(r"(\d[\d\s]{0,6}\d|\d)\s*(р(?![а-яё])|руб|₽|тыс)", s)
    if m:
        n = int(re.sub(r"\s", "", m.group(1)))
        return n * 1000 if m.group(2).startswith("тыс") and n < 100 else n
    for w, n in WORD_NUM.items():
        if re.search(rf"(?<![а-яё]){w}", s) and re.search(r"руб|р(?![а-яё])|₽|тысяч", s):
            return n
    return None


def _number(f, parts, whole):
    where = " ".join(_about(parts, f.get("kw"))) or whole
    unit = f.get("unit", "")
    if "₽" in unit:
        m = _money(where) or _money(whole)
        # «бесплатно» без суммы — это 0 ₽, а не «не сказано»
        return m if m is not None else (0 if FREE.search(where if _about(parts, f.get("kw")) else whole) else None)
    rx = {"кг": r"(\d+)\s*(кг|кило)", "мин": r"(\d+)\s*мин"}.get(unit, r"(\d+)\s*(-?\s*этаж|эт\b)" if f["id"] == "floors" else r"(\d+)")
    m = re.search(rx, where) or re.search(rx, whole)
    return int(m.group(1)) if m else None


def _time(f, parts, whole):
    for p in _about(parts, f.get("kw")):
        m = re.search(r"(\d{1,2})[:.](\d{2})", p) or re.search(r"(?:с|после|до|в|к)\s+(\d{1,2})(?!\d)", p)
        if m:
            h = int(m.group(1))
            mm = m.group(2) if m.lastindex and m.lastindex >= 2 else "00"
            if 0 <= h <= 23:
                return f"{h:02d}:{mm}"
    return None


def parse(topic: dict, text: str) -> list[dict]:
    """[{id, label, type, value|None, unit}] — value None значит «не сказано»."""
    parts, whole = _parts(text), text.lower().replace("ё", "е")
    out = []
    for f in topic["fields"]:
        if f["type"] == "choice":
            v = _choice(f, parts, whole)
        elif f["type"] == "number":
            v = _number(f, parts, whole)
        elif f["type"] == "time":
            v = _time(f, parts, whole)
        else:
            v = text.strip() or None
        out.append({"id": f["id"], "label": f["label"], "type": f["type"], "unit": f.get("unit", ""), "value": v,
                    "options": f.get("options")})
    return out


def summary(fields: list[dict]) -> str:
    """Поля → одна фраза для гостя: «Собаки — да, вес до 10 кг, доплата 1 000 ₽ в сутки, кошки — нет»."""
    bits = []
    included = any(f["value"] in ("включён", "бесплатно") for f in fields if f["type"] == "choice")
    for f in fields:
        v = f["value"]
        if v in (None, ""):
            continue
        if f["type"] == "text":
            return str(v)
        if f["type"] == "number" and v == 0 and "₽" in f["unit"]:
            if included:      # «завтрак — включён» уже сказал, что платить не нужно
                continue
            bits.append(f"{f['label'].lower()} — бесплатно")
            continue
        if f["type"] == "number":
            n = f"{v:,}".replace(",", " ") if isinstance(v, int) else v
            bits.append(f"{f['label'].lower()} {n} {f['unit']}".strip())
        else:
            bits.append(f"{f['label'].lower()} — {v}")
    s = ", ".join(bits)
    return s[:1].upper() + s[1:] if s else ""
