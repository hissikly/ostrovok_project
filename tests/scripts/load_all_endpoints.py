"""Нагрузка по всем GET-эндпоинтам из OpenAPI на всех отелях + ключевые POST. Выход: коды, p50/p95, ошибки."""
import json, sys, time, random, statistics, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

B = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
THREADS = int(sys.argv[2]) if len(sys.argv) > 2 else 32
N_HOTELS = int(sys.argv[3]) if len(sys.argv) > 3 else 9999


def req(method, path, body=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(B + path, data=data, method=method, headers={"Content-Type": "application/json"})
    t = time.time()
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            resp.read()
            return resp.status, time.time() - t
    except urllib.error.HTTPError as e:
        e.read()
        return e.code, time.time() - t
    except Exception as e:
        return f"EXC {type(e).__name__}", time.time() - t


def get_json(path):
    with urllib.request.urlopen(B + path, timeout=60) as r:
        return json.loads(r.read())


hotels = get_json("/api/hotels")
hotels = hotels if isinstance(hotels, list) else hotels.get("hotels") or hotels.get("items")
ids = [h["id"] for h in hotels][:N_HOTELS]
print("hotels:", len(ids))

per_hotel = ["/api/hotels/{id}", "/api/hotels/{id}/facts", "/api/hotels/{id}/faq", "/api/hotels/{id}/conflicts",
             "/api/hotels/{id}/day", "/api/hotels/{id}/day/route", "/api/hotels/{id}/request", "/api/hotels/{id}/reviews",
             "/api/hotels/{id}/sights", "/api/hotels/{id}/web", "/api/hotels/{id}/agent", "/api/hotels/{id}/beach-route",
             "/api/hotels/{id}/window", "/api/hotelier/{id}", "/api/hotelier/{id}/questions", "/api/hotelier/{id}/bookings",
             "/api/hotels/{id}/web/search?q=%D0%B7%D0%B0%D0%B2%D1%82%D1%80%D0%B0%D0%BA"]
glob = ["/api/hotels", "/api/lenses", "/api/interests", "/api/knowledge/topics", "/api/characteristics",
        "/api/characteristics/tools", "/api/sights", "/api/climate/rain", "/api/web/stats", "/api/feedback/stats",
        "/api/profile", "/api/profile/stats", "/api/bookings", "/health", "/", "/#extranet/x"]
posts = [("/api/search", {"lenses": ["sea_view"]}), ("/api/describe", {"text": "тихий номер с видом на закат недалеко от моря"}),
         ("/api/trip/fit", {"interests": ["beach"]})]

jobs = [("GET", p.format(id=i), None) for i in ids for p in per_hotel] + [("GET", g, None) for g in glob] * 5
jobs += [("POST", p, b) for p, b in posts] * 20
jobs += [("POST", f"/api/hotels/{i}/ask", {"text": "можно с собакой?"}) for i in random.sample(ids, min(30, len(ids)))]
jobs += [("POST", "/api/compare", {"ids": random.sample(ids, 3)}) for _ in range(30)]
random.shuffle(jobs)
print("requests:", len(jobs), "threads:", THREADS)

t0 = time.time()
with ThreadPoolExecutor(THREADS) as ex:
    res = list(ex.map(lambda j: (j, *req(*j)), jobs))
wall = time.time() - t0

codes = {}
for j, c, dt in res:
    codes[c] = codes.get(c, 0) + 1
lat = sorted(dt for _, c, dt in res if c == 200)
print("wall %.1f s, rps %.0f" % (wall, len(res) / wall))
print("codes:", codes)
if lat:
    print("p50 %.0f ms, p95 %.0f ms, max %.0f ms" % (statistics.median(lat) * 1e3, lat[int(len(lat) * .95)] * 1e3, lat[-1] * 1e3))
bad = {}
for j, c, dt in res:
    if c != 200:
        key = (j[0], j[1].split("?")[0].replace(next((i for i in ids if i in j[1]), "§"), "{id}"), c)
        bad.setdefault(key, []).append(j[1])
for k, v in sorted(bad.items(), key=lambda kv: -len(kv[1]))[:30]:
    print(len(v), k, v[0])
