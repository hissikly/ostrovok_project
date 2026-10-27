"""Переносит посчитанные профили горизонта в демо-данные сервиса.

Вход: data/derived/okno/*.json (compute_all.py).
Выход: data/seed/okno/<hotel_id>.json — лучи для карты и закат для API «вид из окна»
       data/seed/facts_okno.json       — факты «вид на море», «закат из окна»
Лучи храним компактно: [азимут, тип препятствия b|t|s, дистанция с шагом 5 м, видно море 0|1] —
углы нужны только для расчёта заката, он уже посчитан.
"""
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from astral import Observer
from astral.sun import azimuth, sunset

ROOT = Path(__file__).resolve().parents[3]
SEED = ROOT / "data/seed"
SIDE_RU = {"N": "северная", "E": "восточная", "S": "южная", "W": "западная"}
SIDE_GEN = {"N": "северной", "E": "восточной", "S": "южной", "W": "западной"}
TZ = ZoneInfo("Europe/Moscow")
# Окно видно из комнаты примерно на ±60° от его оси: солнце дальше — только если прижаться к стеклу.
# Такой закат не «из окна»: sets_into_sea снимаем, hidden_by = "aside"
ASIDE_DEG = 60


def aside(sun: list, normal_az: float, lat: float, lon: float) -> list:
    """Добавляет к закату по месяцам азимут солнца и угол от оси окна (минус — левее, если смотреть из окна)."""
    obs = Observer(latitude=lat, longitude=lon, elevation=0)
    out = []
    for s in sun:
        az = azimuth(obs, sunset(obs, dt.date(2026, s["month"], 15), tzinfo=TZ))
        off = (az - normal_az + 540) % 360 - 180
        s = {**s, "sunset_az": round(az), "off_window": round(off)}
        if ASIDE_DEG < abs(off) <= 90 and s["sun_hidden_at"]:   # дальше 90° — за стеной, это «не видно»
            s.update(sets_into_sea=False, hidden_by="aside", side="left" if off < 0 else "right")
        out.append(s)
    return out


def confidence(nearby: dict) -> float:
    """Чем больше соседних домов с известной высотой, тем выше уверенность."""
    n = max(1, nearby["count"])
    return round((0.9 * nearby["height"] + 0.75 * nearby["levels"] + 0.45 * nearby["default"]) / n, 2)


def view(shares: dict) -> tuple:
    """(с какого этажа море в окне, с какого — краешком) по долям моря на этажах одной стороны."""
    from_floor = next((fl for fl in sorted(shares) if shares[fl] >= 0.3), None)      # нормальный вид
    glimpse_from = next((fl for fl in sorted(shares) if shares[fl] >= 0.05), None)  # краешком
    return from_floor, glimpse_from


def sea_confidence(base: float, facades: dict, levels_guessed: bool) -> float:
    """Уверенность «вида на море» отеля — одна на все стороны: сервис судит об отеле по лучшей стороне.
    Сверка с разметкой по фото (features/metrics) показала, что в этих случаях расчёт ошибается чаще, —
    понижаем, чтобы ответ ушёл в «слабые» и вопрос отельеру: у отеля только краешек моря; этажность
    не знаем (считали 5); море видно лишь с верхнего этажа; «моря не видно» у здания в 1–2 этажа —
    у отелей в OSM часто размечена только нижняя часть."""
    views = [view({int(fl): v["sea_share"] for fl, v in f["floors"].items()}) for f in facades.values()]
    full = [v[0] for v in views if v[0]]
    glimpse = any(v[1] for v in views)
    top = max(int(fl) for f in facades.values() for fl in f["floors"])
    k = 1.0
    if glimpse and not full:
        k *= 0.75
    if levels_guessed:
        k *= 0.85
    if full and min(full) == top:
        k *= 0.9
    if not glimpse and top <= 2:
        k *= 0.85
    return round(base * k, 2)


def hotel_id(osm: str) -> str:
    t, i = osm.split("/")
    return f"{t[0]}{i}"


def main():
    today = dt.date.today()
    facts, n = [], 0
    (SEED / "okno").mkdir(parents=True, exist_ok=True)
    for old in (SEED / "okno").glob("*.json"):
        old.unlink()
    for src in sorted((ROOT / "data/derived/okno").glob("*.json")):
        d = json.load(open(src))
        if not d["facades"]:
            continue
        hid = hotel_id(d["hotel"]["osm"])
        guessed = d["hotel"]["levels_src"].startswith("нет данных")
        conf = round(confidence(d["buildings_nearby"]) * (0.85 if guessed else 1), 2)
        sea_conf = sea_confidence(confidence(d["buildings_nearby"]), d["facades"], guessed)
        evidence_base = {"dem": "Copernicus GLO-30", "buildings": d["buildings_nearby"],
                         "levels_src": d["hotel"]["levels_src"]}
        out = {"hotel_id": hid, "hotel": d["hotel"], "confidence": conf, "facades": {}}
        for side, f in d["facades"].items():
            floors = {}
            for fl, v in f["floors"].items():
                floors[fl] = {"eye_m": v["eye_m"], "sea_share": v["sea_share"],
                              "blocked_by_buildings": v["blocked_by_buildings"],
                              "sun": aside(v["sun"], f["normal_az"], f["eye_lat"], f["eye_lon"])}
                if "profile" in v:   # лучи для карты — только у нескольких этажей
                    floors[fl]["profile"] = [[int(az), p["kind"][0], int(round(p["dist"] / 5) * 5), int(p["sea"])]
                                             for az, p in sorted(v["profile"].items(), key=lambda x: int(x[0]))]
            out["facades"][side] = {"normal_az": f["normal_az"], "eye": [f["eye_lat"], f["eye_lon"]],
                                    "floors": floors}
            shares = {int(fl): v["sea_share"] for fl, v in f["floors"].items()}
            from_floor, glimpse_from = view(shares)
            facts.append({
                "hotel_id": hid, "scope": f"facade:{side}", "characteristic": "sea_view",
                "value": {"from_floor": from_floor, "glimpse_from": glimpse_from, "share_by_floor": shares,
                          "text": (f"Море видно с {from_floor}-го этажа ({SIDE_RU[side]} сторона)" if from_floor
                                   else f"С {SIDE_GEN[side]} стороны моря почти не видно")},
                "confidence": sea_conf,
                "source": "computed:horizon", "method_version": "horizon@0.3",
                "evidence": evidence_base, "obtained_at": today.isoformat(),
                "valid_until": (today + dt.timedelta(days=180)).isoformat(), "status": "active",
            })
            top = floors[max(floors, key=int)]
            sea_months = [s["month"] for s in top["sun"] if s["sets_into_sea"]]
            if sea_months:
                facts.append({
                    "hotel_id": hid, "scope": f"facade:{side}", "characteristic": "sunset_view",
                    "value": {"months": sea_months, "top_floor": int(max(f["floors"], key=int)),
                              "text": f"Закат над морем из окон {SIDE_GEN[side]} стороны"},
                    "confidence": conf, "source": "computed:horizon+sun", "method_version": "horizon@0.2",
                    "evidence": evidence_base, "obtained_at": today.isoformat(),
                    "valid_until": (today + dt.timedelta(days=180)).isoformat(), "status": "active",
                })
        json.dump(out, open(SEED / "okno" / f"{hid}.json", "w"), ensure_ascii=False, separators=(",", ":"))
        n += 1
    json.dump(facts, open(SEED / "facts_okno.json", "w"), ensure_ascii=False, indent=0)
    print(f"отелей: {n}, фактов: {len(facts)}")


if __name__ == "__main__":
    main()
