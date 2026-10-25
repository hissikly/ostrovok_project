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

ROOT = Path(__file__).resolve().parents[3]
SEED = ROOT / "data/seed"
SIDE_RU = {"N": "северная", "E": "восточная", "S": "южная", "W": "западная"}
SIDE_GEN = {"N": "северной", "E": "восточной", "S": "южной", "W": "западной"}


def confidence(nearby: dict) -> float:
    """Чем больше соседних домов с известной высотой, тем выше уверенность."""
    n = max(1, nearby["count"])
    return round((0.9 * nearby["height"] + 0.75 * nearby["levels"] + 0.45 * nearby["default"]) / n, 2)


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
        conf = confidence(d["buildings_nearby"])
        evidence_base = {"dem": "Copernicus GLO-30", "buildings": d["buildings_nearby"],
                         "levels_src": d["hotel"]["levels_src"]}
        out = {"hotel_id": hid, "hotel": d["hotel"], "confidence": conf, "facades": {}}
        for side, f in d["facades"].items():
            floors = {}
            for fl, v in f["floors"].items():
                floors[fl] = {"eye_m": v["eye_m"], "sea_share": v["sea_share"],
                              "blocked_by_buildings": v["blocked_by_buildings"], "sun": v["sun"],
                              "profile": [[int(az), p["kind"][0], int(round(p["dist"] / 5) * 5), int(p["sea"])]
                                          for az, p in sorted(v["profile"].items(), key=lambda x: int(x[0]))]}
            out["facades"][side] = {"normal_az": f["normal_az"], "eye": [f["eye_lat"], f["eye_lon"]],
                                    "floors": floors}
            shares = {int(fl): v["sea_share"] for fl, v in f["floors"].items()}
            from_floor = next((fl for fl in sorted(shares) if shares[fl] >= 0.3), None)      # нормальный вид
            glimpse_from = next((fl for fl in sorted(shares) if shares[fl] >= 0.05), None)  # краешком
            facts.append({
                "hotel_id": hid, "scope": f"facade:{side}", "characteristic": "sea_view",
                "value": {"from_floor": from_floor, "glimpse_from": glimpse_from, "share_by_floor": shares,
                          "text": (f"Море видно с {from_floor}-го этажа ({SIDE_RU[side]} сторона)" if from_floor
                                   else f"С {SIDE_GEN[side]} стороны моря почти не видно")},
                "confidence": conf, "source": "computed:horizon", "method_version": "horizon@0.1",
                "evidence": evidence_base, "obtained_at": today.isoformat(),
                "valid_until": (today + dt.timedelta(days=180)).isoformat(), "status": "active",
            })
            top = f["floors"][max(f["floors"], key=int)]
            sea_months = [s["month"] for s in top["sun"] if s["sets_into_sea"]]
            if sea_months:
                facts.append({
                    "hotel_id": hid, "scope": f"facade:{side}", "characteristic": "sunset_view",
                    "value": {"months": sea_months, "top_floor": int(max(f["floors"], key=int)),
                              "text": f"Закат над морем из окон {SIDE_GEN[side]} стороны"},
                    "confidence": conf, "source": "computed:horizon+sun", "method_version": "horizon@0.1",
                    "evidence": evidence_base, "obtained_at": today.isoformat(),
                    "valid_until": (today + dt.timedelta(days=180)).isoformat(), "status": "active",
                })
        json.dump(out, open(SEED / "okno" / f"{hid}.json", "w"), ensure_ascii=False, separators=(",", ":"))
        n += 1
    json.dump(facts, open(SEED / "facts_okno.json", "w"), ensure_ascii=False, indent=0)
    print(f"отелей: {n}, фактов: {len(facts)}")


if __name__ == "__main__":
    main()
