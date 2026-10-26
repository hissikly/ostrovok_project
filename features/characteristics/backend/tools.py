"""Реестр инструментов агента-исследователя.

Инструмент — обёртка над тем, что проект уже умеет: расчёт вида из окна, пеший путь, шум, места на карте,
отметки самого отеля в OSM, ответы отеля, сайт отеля, вопрос отельеру. У каждого — описание по-русски:
его читает LLM, когда собирает план новой характеристики, и его же видит гость в трассе «как узнали».

run(hotel, params, spec, mode) → Result:
  status      found — нашли ответ; absent — проверили, и ответ «нет / не нашли»; nothing — источник молчит;
              unavailable — источник ещё не подключён; asked — вопрос ушёл отелю
  value, confidence, source, evidence — как у факта (wiki/architecture.md)
  note        одна фраза для трассы: «На карте: велодорожка в 240 м, 3 мин пешком»
mode: "batch" — прогон по всем отелям (можно задать вопрос отелю), "view" — только посмотреть (без побочных эффектов).
"""
import importlib
import logging
from dataclasses import dataclass, field
from functools import lru_cache

from core.seed import load
from features.facts.backend import facts_for

from .geo import Finder, known_tags, layers

log = logging.getLogger(__name__)

FOUND, ABSENT, NOTHING, UNAVAILABLE, ASKED = "found", "absent", "nothing", "unavailable", "asked"


def result(status, note, value=None, confidence=None, source=None, evidence=None):
    return {"status": status, "note": note, "value": value, "confidence": confidence, "source": source,
            "evidence": evidence or {}}


@dataclass
class Tool:
    id: str
    title: str          # для гостя: «Карта города», «Сайт отеля»
    about: str          # для LLM и для экрана «добавить характеристику»
    params: dict = field(default_factory=dict)   # имя → описание
    kinds: tuple = ()   # какие типы характеристик умеет: near / yes_no / computed

    def available(self) -> bool:
        return True

    def run(self, hotel, params, spec, mode="batch") -> dict:
        raise NotImplementedError

    def describe(self) -> dict:
        return {"id": self.id, "title": self.title, "about": self.about, "params": self.params,
                "kinds": list(self.kinds), "available": self.available()}


# --- расчёты, которые уже сделали другие фичи -----------------------------------------------------

class FactTool(Tool):
    """Читает готовый расчёт другой фичи из хранилища фактов (вид из окна, путь до пляжа, шум)."""

    def __init__(self, id, title, about, chars, word):
        super().__init__(id, title, about, {"characteristic": f"одна из: {', '.join(chars)}"}, ("computed",))
        self.chars, self.word = chars, word

    def run(self, hotel, params, spec, mode="batch"):
        char = params.get("characteristic") or self.chars[0]
        fs = [f for f in facts_for(hotel["id"]) if f["characteristic"] == char and f["status"] == "active"]
        if not fs:
            return result(NOTHING, f"{self.word}: для этого отеля ещё не посчитали")
        best = max(fs, key=lambda f: f["confidence"])
        return result(FOUND, f"{self.word}: посчитано", value={"facts": [f["id"] for f in fs]},
                      confidence=min(f["confidence"] for f in fs), source=best["source"],
                      evidence={"facts": [f["id"] for f in fs]})


# --- карта: любое место или линия из OSM ---------------------------------------------------------------

class PoiNearby(Tool):
    def __init__(self):
        super().__init__(
            "poi_nearby", "Карта города",
            "Ищет на открытой карте OSM ближайшее к отелю место или линию с нужными тегами "
            "(велодорожка, стройка, теннисный корт, кальянная…) и считает время пешком по улицам с подъёмами.",
            {"osm": "список тегов OSM «ключ=значение», например [\"highway=cycleway\"]",
             "kind": "как назвать место по-русски, в именительном падеже: «Велодорожка»",
             "match_min": "до скольких минут пешком — «рядом»", "partial_min": "до скольких — «можно дойти»"},
            ("near",))
        self._finders = {}

    def finder(self, params) -> Finder:
        key = (tuple(sorted(params["osm"])), params["partial_min"])
        if key not in self._finders:
            self._finders = {key: Finder(list(key[0]), key[1])}   # держим один: прогон идёт по одной спеке
        return self._finders[key]

    def run(self, hotel, params, spec, mode="batch"):
        tags = known_tags()
        total = sum(tags.get(t, 0) for t in params["osm"])
        kind = params.get("kind") or spec["title"]
        if not total:
            return result(NOTHING, f"На открытой карте Сочи «{kind.lower()}» не отмечено нигде — карта тут не поможет")
        r = self.finder(params).nearest(hotel["lat"], hotel["lon"])
        obtained = layers()[0]
        if r["found"]:
            graph = r["by"] == "graph"
            value = {"meters": r["meters"], "walk_min": r["walk_min"], "name": r["name"], "kind": kind,
                     "lat": r["lat"], "lon": r["lon"], "count": r["count"]}
            name = f" «{r['name']}»" if r["name"] else ""
            return result(FOUND, f"На карте: {kind.lower()}{name} в {_dist(r['meters'])}, {r['walk_min']} мин пешком",
                          value, 0.8 if graph else 0.7, "computed:osm-poi+walk" if graph else "computed:osm-poi",
                          {"osm": r["osm"], "tag": r["tag"], "obtained_at": obtained,
                           "method": "пешеходный граф OSM, время по Тоблеру" if graph else "по прямой ×1,3"})
        # «не нашли» честно, но с оговоркой: редкие на карте вещи могли просто не нанести
        conf = 0.55 if total >= 20 else 0.35
        value = {"meters": None, "within_min": params["partial_min"], "kind": kind, "count": 0}
        rare = "" if total >= 20 else " (на карте такое отмечают редко)"
        return result(ABSENT, f"На карте в {params['partial_min']} мин пешком не нашли{rare}", value, conf,
                      "computed:osm-poi+walk", {"tags": params["osm"], "obtained_at": obtained})


def _dist(m):
    return f"{m} м" if m < 1000 else f"{m / 1000:.1f} км".replace(".", ",")


# --- что отель сам отметил о себе на карте ---------------------------------------------------------

@lru_cache(maxsize=1)
def hotel_tags() -> dict:
    return load("hotel_tags.json") or {}


class HotelOsm(Tool):
    def __init__(self):
        super().__init__(
            "hotel_osm", "Отметки отеля на карте",
            "Читает, что о самом отеле отмечено в OSM: wifi (internet_access), доступная среда (wheelchair), "
            "курение (smoking), кондиционер (air_conditioning), число номеров (rooms), способы оплаты (payment:*).",
            {"key": "тег OSM отеля, например internet_access", "yes": "значения, которые значат «да»",
             "no": "значения, которые значат «нет»"},
            ("yes_no",))

    def run(self, hotel, params, spec, mode="batch"):
        v = hotel_tags().get(hotel["id"], {}).get(params["key"])
        if v is None:
            return result(NOTHING, "В карточке отеля на карте об этом ничего нет")
        if v in params.get("yes", []):
            ans = True
        elif v in params.get("no", []):
            ans = False
        else:
            return result(NOTHING, f"В карточке отеля на карте непонятная отметка «{v}»")
        return result(FOUND if ans else ABSENT, f"На карте у отеля отмечено: {'да' if ans else 'нет'}",
                      {"answer": ans}, 0.6, "osm", {"tag": f"{params['key']}={v}", "osm": hotel["osm"]})


# --- ответы отеля и общее знание (features/knowledge) ---------------------------------------------

class HotelAnswers(Tool):
    def __init__(self):
        super().__init__(
            "hotel_answers", "Ответы отеля",
            "Ищет в базе знаний: что отель уже ответил гостям (раздел «Для отелей»), что мы посчитали сами, "
            "общее знание о Сочи.",
            {"question": "вопрос по-русски, как его задал бы гость"},
            ("yes_no",))

    def run(self, hotel, params, spec, mode="batch"):
        from features.knowledge.backend import ask
        a = ask(hotel["id"], params.get("question") or spec["question"], {})
        ok = [x for x in a.get("answers", []) if x.get("status") == "answered"]
        if not ok:
            return result(NOTHING, "Отель на этот вопрос ещё не отвечал")
        x = ok[0]
        ans = _yes_no(x.get("text", ""))
        who = {"hotel": "Отель ответил", "computed": "Уже посчитали"}.get(x.get("level"), "Общее знание")
        return result(FOUND if ans is not False else ABSENT, f"{who}: «{x['text']}»",
                      {"answer": ans, "text": x["text"]}, x.get("confidence") or 0.6, x.get("source") or "hotelier",
                      {"level": x.get("level"), "topic": x.get("topic")})


def _yes_no(text: str):
    t = text.lower().strip()
    if t.startswith(("нет", "не ", "к сожалению")) or " нет" in t[:25]:
        return False
    if t.startswith(("да", "есть", "можно", "конечно")):
        return True
    return None


# --- сайт отеля (бриф 2, features/web_sources) ----------------------------------------------------

class WebText(Tool):
    def __init__(self):
        super().__init__(
            "web_text", "Сайт отеля",
            "Ищет ответ на официальном сайте отеля; факт — только дословная цитата со ссылкой на страницу.",
            {"question": "вопрос по-русски"}, ("yes_no",))

    def _mod(self):
        try:
            return importlib.import_module("features.web_sources.backend")
        except ImportError:
            return None

    def available(self):
        m = self._mod()
        return bool(m and hasattr(m, "answer"))

    def run(self, hotel, params, spec, mode="batch"):
        m = self._mod()
        if not m or not hasattr(m, "answer"):
            return result(UNAVAILABLE, "Сайты отелей пока не подключены")
        if not hotel.get("website"):
            return result(NOTHING, "У отеля нет сайта в открытых данных")
        try:
            a = m.answer(hotel["id"], params.get("question") or spec["question"])
        except Exception as e:  # чужой модуль не должен ронять прогон
            log.warning("web_text: %s", e)
            a = None
        if not a or not a.get("quote"):
            return result(NOTHING, "На сайте отеля ответа не нашли")
        ans = a.get("answer")
        return result(ABSENT if ans is False else FOUND, f"На сайте отеля: «{a['quote']}»",
                      {"answer": ans, "text": a.get("text") or a["quote"]}, a.get("confidence", 0.6),
                      a.get("source") or "web", {"url": a.get("url"), "quote": a["quote"]})


# --- погода (бриф 4, features/climate) --------------------------------------------------------------

class Climate(Tool):
    def __init__(self):
        super().__init__("climate", "Погода и море по месяцам",
                         "Температура воздуха и воды, дожди по месяцам — одно на весь город.", {}, ("computed",))

    def available(self):
        try:
            return hasattr(importlib.import_module("features.climate.backend"), "month")
        except ImportError:
            return False

    def run(self, hotel, params, spec, mode="batch"):
        return result(UNAVAILABLE, "Погода по месяцам пока не подключена")


# --- спросить у отеля (features/hotelier) -----------------------------------------------------------

class AskHotelier(Tool):
    def __init__(self):
        super().__init__(
            "ask_hotelier", "Вопрос отелю",
            "Последний шаг: если открытые данные молчат — вопрос уходит отелю в раздел «Для отелей». "
            "Ответ отеля станет фактом.",
            {"question": "вопрос отелю на «вы»"}, ("yes_no", "near"))

    def run(self, hotel, params, spec, mode="batch"):
        q = params.get("question") or spec.get("ask_hotelier") or spec["question"]
        if mode != "batch":
            return result(ASKED, "Спросили у отеля, ждём ответа")
        from features.hotelier.backend import ask_hotel
        ask_hotel(hotel["id"], None, q, origin="agent")
        return result(ASKED, "Открытые данные молчат — спросили у отеля")


TOOLS = {t.id: t for t in [
    FactTool("viewshed", "Вид из окна", "Профиль горизонта по рельефу и высоте соседних домов: "
             "с какого этажа и с какой стороны видно море, виден ли закат над морем.",
             ["sea_view", "sunset_view"], "Вид из окна"),
    FactTool("walk_route", "Путь пешком", "Пеший путь до пляжа по улицам и лестницам: минуты туда и обратно, подъём.",
             ["beach_route", "beach_distance"], "Путь до пляжа"),
    FactTool("noise_model", "Шум по карте", "Оценка ночного шума по сторонам здания: дороги, железная дорога, "
             "бары, аэропорт рядом.", ["noise"], "Шум"),
    PoiNearby(), HotelOsm(), HotelAnswers(), WebText(), Climate(), AskHotelier(),
]}


def registry() -> list[dict]:
    return [t.describe() for t in TOOLS.values()]
