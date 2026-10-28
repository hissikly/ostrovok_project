"""Находит дубли: одно здание в OSM отмечено дважды (точкой и контуром, два контура одного корпуса)
→ data/seed/hotel_dups.json {скрытый id: оставленный id}.

Дубль — одно и то же название (без «отель», «гостиница», кавычек) ближе 50 м.
Оставляем запись, у которой больше фактов; при равенстве — с «О!кном», потом с контуром здания.
Скрытый отель не попадает в выдачу и на карту, но по ссылке и в старых бронях открывается.

Запуск (после всех pipeline-скриптов фактов):
    .venv/bin/python features/hotels/pipeline/dedup.py
"""
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import app.main  # noqa: E402,F401  подключает провайдеров фактов
from features.facts.backend import facts_for  # noqa: E402

SEED = ROOT / "data/seed"
NEAR_M = 50


def norm(name):
    n = re.sub(r"\b(отель|гостиница|hotel)\b", " ", name.lower().replace("ё", "е"))
    return " ".join(re.sub(r"[«»\"'.,\-–—]", " ", n).split())


def dist(a, b):
    k = math.cos(math.radians(a["lat"]))
    return 6371000 * math.hypot(math.radians(b["lat"] - a["lat"]), math.radians(b["lon"] - a["lon"]) * k)


def main():
    hs = json.load(open(SEED / "hotels.json", encoding="utf-8"))
    okno = {p.stem for p in (SEED / "okno").glob("*.json")}
    score = {h["id"]: (len(facts_for(h["id"])), h["id"] in okno, h["has_contour"]) for h in hs}
    keep = {}                                    # id → кого оставляем вместо него
    for i, a in enumerate(hs):
        for b in hs[i + 1:]:
            if norm(a["name"]) == norm(b["name"]) and dist(a, b) < NEAR_M:
                ka, kb = keep.get(a["id"], a["id"]), keep.get(b["id"], b["id"])
                if ka == kb:
                    continue
                win, lose = (ka, kb) if score[ka] >= score[kb] else (kb, ka)
                for x, y in list(keep.items()):
                    if y == lose:
                        keep[x] = win
                keep[lose] = win
    json.dump(dict(sorted(keep.items())), open(SEED / "hotel_dups.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    name = {h["id"]: h["name"] for h in hs}
    for x, y in sorted(keep.items(), key=lambda kv: name[kv[0]]):
        print(f"{name[x]}: скрыт {x} ({score[x][0]} фактов) → оставлен {y} ({score[y][0]})")
    print(f"скрыто дублей: {len(keep)}, в выдаче: {len(hs) - len(keep)}")


if __name__ == "__main__":
    main()
