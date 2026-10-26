"""Утро в окне: во сколько солнце заглянет в окно каждой стороны (офлайн, по профилям «О!кна»).

Берёт полные профили горизонта из data/derived/okno/<id>.json (угол закрытия по каждому азимуту
в секторе окна ±80°) и для 15-го числа каждого месяца ищет первую минуту после восхода, когда
солнце выше этого угла. Результат — data/seed/day_morning.json (килобайты, в git):
  {hotel_id: {"sunrise": [восход по месяцам 1..12], side: {floor: [солнце_в_окне|null по месяцам]}}}
null — до полудня солнце в это окно не попадает (окно на запад или солнце закрыто домами/склоном).

Запуск: .venv/bin/python features/day/pipeline/morning_sun.py
"""
import datetime as dt
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from astral import Observer
from astral.sun import azimuth, elevation, sunrise

ROOT = Path(__file__).resolve().parents[3]
DERIVED = ROOT / "data" / "derived" / "okno"
OUT = ROOT / "data" / "seed" / "day_morning.json"
TZ = ZoneInfo("Europe/Moscow")
MONTHS = range(1, 13)


def sun_in(obs, profile, day):
    """(восход, первая минута солнца в окне до 12:00 или None)."""
    sr = sunrise(obs, day, tzinfo=TZ)
    t, noon = sr - dt.timedelta(minutes=5), dt.datetime.combine(day, dt.time(12), TZ)
    while t < noon:
        p = profile.get(str(int(round(azimuth(obs, t))) % 360))
        if p is not None and elevation(obs, t) > p["angle"]:
            return sr, max(t, sr)
        t += dt.timedelta(minutes=2)
    return sr, None


def hotel(path):
    d = json.load(open(path, encoding="utf-8"))
    out = {"sunrise": None}
    for side, f in d["facades"].items():
        obs = Observer(latitude=f["eye_lat"], longitude=f["eye_lon"], elevation=0)
        floors = {}
        for fl, v in f["floors"].items():
            if "profile" not in v:
                continue
            rows, rises = [], []
            for m in MONTHS:
                sr, t = sun_in(obs, v["profile"], dt.date(2026, m, 15))
                rises.append(sr.strftime("%H:%M"))
                rows.append(t.strftime("%H:%M") if t else None)
            floors[fl] = rows
            out["sunrise"] = out["sunrise"] or rises
        out[side] = floors
    return out


def main():
    files = sorted(DERIVED.glob("*.json"))
    if not files:
        sys.exit(f"нет профилей в {DERIVED}: сначала features/okno/pipeline/compute_all.py")
    res = {p.stem: hotel(p) for p in files}
    OUT.write_text(json.dumps({"obtained_at": dt.date.today().isoformat(), "hotels": res},
                              ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"day_morning: {len(res)} отелей → {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} КБ)")


if __name__ == "__main__":
    main()
