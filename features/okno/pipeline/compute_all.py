"""Вид из окна для всех отелей с контуром здания в OSM → data/derived/okno/<hotel_id>.json.

    .venv/bin/python features/okno/pipeline/compute_all.py          # только непосчитанные
    .venv/bin/python features/okno/pipeline/compute_all.py --force  # пересчитать всё
Потом: features/okno/pipeline/export_seed.py → data/seed/ (то, что видит сервис).
"""
import json
import os
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import window  # noqa: E402

OUT = window.ROOT / "data/derived/okno"


def hotel_id(osm_ref: str) -> str:
    t, i = osm_ref.split("/")
    return f"{t[0]}{i}"


def job(osm_ref: str):
    t = time.time()
    try:
        r = window.compute(osm_ref)
    except Exception:
        return osm_ref, None, traceback.format_exc(limit=2)
    if r is None:
        return osm_ref, None, "нет контура"
    json.dump(r, open(OUT / f"{hotel_id(osm_ref)}.json", "w"), ensure_ascii=False)
    return osm_ref, round(time.time() - t, 1), None


def main():
    force = "--force" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    refs = [ref for ref, h in window.hotels().items()
            if h.get("tags", {}).get("tourism") == "hotel" and h["type"] != "node" and window.poly_of(h)]
    todo = [r for r in refs if force or not (OUT / f"{hotel_id(r)}.json").exists()]
    print(f"отелей с контуром: {len(refs)}, считать: {len(todo)}", flush=True)
    t0, ok, fail = time.time(), 0, []
    workers = max(1, (os.cpu_count() or 2) - 1)
    with ProcessPoolExecutor(workers) as ex:
        for n, fut in enumerate(as_completed([ex.submit(job, r) for r in todo]), 1):
            ref, sec, err = fut.result()
            if err:
                fail.append((ref, err.strip().splitlines()[-1]))
            else:
                ok += 1
            if n % 20 == 0 or n == len(todo):
                print(f"  {n}/{len(todo)} готово, {time.time() - t0:.0f} с", flush=True)
    print(f"посчитано: {ok}, ошибок: {len(fail)}")
    for ref, e in fail:
        print(f"  {ref}: {e}")


if __name__ == "__main__":
    main()
