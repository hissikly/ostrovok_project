"""Спецификации характеристик: что спрашиваем, каким планом ищем ответ, когда верим результату.

Встроенные — features/characteristics/specs/*.yaml (вид на море, закат, пляж, шум, Wi-Fi) и каталог
«что рядом» (features/nearby/specs.json, 36 фильтров). Добавленные описанием — DATA/runtime/characteristics/.

Поля:
  id, title, question          — латиница; как назвать гостю; вопрос гостя
  kind                         — near (место рядом) | yes_no (да / нет об отеле) | computed (считает другая фича)
  prefer                       — для near: near («хорошо, если рядом») или far («хорошо, если далеко»: стройка, ЛЭП)
  plan: [{tool, params}]       — инструменты по порядку; стоп на первом уверенном ответе
  min_confidence, ttl_days     — порог уверенности; срок годности факта
  ask_hotelier                 — вопрос отелю, если открытые данные молчат
  icon, group, synonyms        — для линзы в «Ещё фильтры» и для «✨ опиши»
"""
import re
from functools import lru_cache
from pathlib import Path

import yaml

from features.nearby.backend import specs as nearby_specs

from .geo import known_tags
from .tools import TOOLS

SPECS = Path(__file__).resolve().parents[1] / "specs"
KINDS = ("near", "yes_no", "computed")
ICONS = {"pin", "mountain", "waves", "sunset", "building", "window", "beach", "star", "cart", "card", "cup", "tree",
         "dumbbell", "child", "pill", "health", "moon", "bus", "car", "paw", "basket", "bag", "box", "fork", "burger",
         "glass", "film", "tooth", "train", "parking", "fuel", "bolt", "bike", "church", "mail", "hospital", "landmark",
         "cross", "clock", "volume", "snow", "users", "mute", "x", "question", "check"}
GROUPS = ("Магазины", "Еда", "Отдых", "Дети", "Здоровье", "Ночью", "Транспорт", "Питомцы", "Прочее")


@lru_cache(maxsize=1)
def builtin() -> list[dict]:
    out = [validate({**yaml.safe_load(open(p, encoding="utf-8")), "origin": "builtin"})[0]
           for p in sorted(SPECS.glob("*.yaml"))]
    # каталог «что рядом» — тоже характеристики, только описаны в своей фиче
    for s in nearby_specs():
        out.append({"id": s["id"], "title": s["title"], "question": f"{s['title']}?", "kind": "near", "prefer": "near",
                    "icon": s["icon"], "group": s["group"], "synonyms": s["synonyms"], "origin": "nearby",
                    "plan": [{"tool": "poi_nearby", "params": {"osm": s["osm"], "kind": s["kind"],
                                                               "match_min": s["match_min"],
                                                               "partial_min": s["partial_min"]}}],
                    "min_confidence": 0.45, "ttl_days": 180})
    return out


def validate(spec: dict, taken: set[str] = frozenset()) -> tuple[dict, list[str], list[str]]:
    """Спека, ошибки (сохранять нельзя), предупреждения (можно, но стоит знать). Чинит мелочи сама."""
    errors, warnings = [], []
    s = {k: v for k, v in spec.items() if v is not None}
    s["id"] = re.sub(r"[^a-z0-9_]", "_", str(s.get("id", "")).lower()).strip("_")[:40]
    if not s["id"]:
        errors.append("Нет id")
    elif s["id"] in taken:
        errors.append(f"Характеристика «{s['id']}» уже есть")
    for k in ("title", "question"):
        if not str(s.get(k, "")).strip():
            errors.append(f"Нет поля {k}")
    if s.get("kind") not in KINDS:
        errors.append(f"kind должен быть одним из {', '.join(KINDS)}")
    s.setdefault("prefer", "near")
    if s["prefer"] not in ("near", "far"):
        s["prefer"] = "near"
    if s.get("icon") not in ICONS:
        s["icon"] = "pin" if s.get("kind") == "near" else "question"
    if s.get("group") not in GROUPS:
        s["group"] = "Прочее"
    s["synonyms"] = [str(x).lower() for x in s.get("synonyms") or []][:20]
    s["min_confidence"] = min(max(float(s.get("min_confidence", 0.5)), 0.1), 0.95)
    s["ttl_days"] = int(s.get("ttl_days", 180))
    plan = s.get("plan") or []
    if not plan:
        errors.append("Пустой план: не знаем, где искать ответ")
    tags = known_tags()
    for i, step in enumerate(plan):
        tool = TOOLS.get(step.get("tool"))
        if tool is None:
            errors.append(f"Шаг {i + 1}: нет инструмента «{step.get('tool')}»")
            continue
        p = step.setdefault("params", {}) or {}
        step["params"] = p
        if tool.id == "poi_nearby":
            p["osm"] = [t for t in p.get("osm") or [] if re.fullmatch(r"[a-z_:]+=[a-z0-9_;:-]+", str(t))]
            if not p["osm"]:
                errors.append("Карта: не указаны теги OSM")
            missing = [t for t in p["osm"] if not tags.get(t)]
            if missing and len(missing) == len(p["osm"]):
                warnings.append(f"На карте Сочи нет ни одного места с тегами {', '.join(missing)} — "
                                "карта не поможет, ответ придётся спрашивать у отелей")
            elif missing:
                warnings.append(f"Тегов {', '.join(missing)} на карте Сочи нет — ищем по остальным")
            p.setdefault("kind", s.get("title", ""))
            p["match_min"] = int(p.get("match_min") or 5)
            p["partial_min"] = max(int(p.get("partial_min") or p["match_min"] * 2), p["match_min"])
            if p["partial_min"] > 40:
                p["partial_min"] = 40
                warnings.append("Дальше 40 минут пешком не ищем")
        for flag, name in ((True, "yes"), (False, "no")):   # YAML 1.1 читает ключи yes / no как true / false
            if flag in p:
                p[name] = p.pop(flag)
        if tool.id == "hotel_osm" and not p.get("key"):
            errors.append("Отметки отеля: не указан тег")
        if not tool.available():
            warnings.append(f"«{tool.title}» пока не подключён — шаг пропустим")
    if s.get("kind") == "near" and not any(st.get("tool") == "poi_nearby" for st in plan):
        errors.append("Для места рядом нужен шаг «Карта города»")
    return s, errors, warnings


def human(spec: dict) -> list[str]:
    """План по-человечески — для предпросмотра перед «Посчитать для всех»."""
    out = []
    for step in spec.get("plan", []):
        t, p = TOOLS.get(step["tool"]), step.get("params", {})
        if t is None:
            continue
        if t.id == "poi_nearby":
            what = p.get("kind", spec["title"]).lower()
            out.append(f"Ищем на карте: {what} — до {p['match_min']} мин пешком «рядом», до {p['partial_min']} — «можно дойти»")
        elif t.id == "hotel_osm":
            out.append("Смотрим, что отель сам отметил о себе на карте")
        elif t.id == "hotel_answers":
            out.append("Ищем в ответах отеля и в базе знаний")
        elif t.id == "web_text":
            out.append("Ищем на сайте отеля — только дословные цитаты" + ("" if t.available() else " (пока не подключено)"))
        elif t.id == "ask_hotelier":
            out.append(f"Не нашли — спрашиваем у отеля: «{p.get('question') or spec.get('ask_hotelier') or spec['question']}»")
        else:
            out.append(f"{t.title}: берём готовый расчёт")
    return out
