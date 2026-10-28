"""Плохие входы: несуществующие id, мусор в параметрах, длинный текст, юникод, инъекции. Ищем 500 и исключения."""
import json, sys, urllib.request, urllib.error, urllib.parse

B = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
q = urllib.parse.quote


def req(method, path, body=None, raw=None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    r = urllib.request.Request(B + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=90) as resp:
            return resp.status, resp.read()[:300]
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:300]
    except Exception as e:
        return "EXC " + type(e).__name__, b""


with urllib.request.urlopen(B + "/api/hotels") as r:
    hs = json.loads(r.read())
H = hs[0]["id"]
BAD_IDS = ["nope", "../../etc/passwd", "%2e%2e%2fetc%2fpasswd", "' OR 1=1 --", "<script>alert(1)</script>", "😀" * 50, "a" * 5000, "0", "-1"]
LONG = "море " * 20000
WEIRD = ["", " ", LONG, "'; drop table questions; --", "<img src=x onerror=alert(1)>", "\u0000‮", "😀🏖️" * 200, "{{7*7}}", "%s%s%n"]

cases = []
for bid in BAD_IDS:
    e = q(bid, safe="")
    for p in ["/api/hotels/{}", "/api/hotels/{}/facts", "/api/hotels/{}/faq", "/api/hotels/{}/day", "/api/hotels/{}/day/route",
              "/api/hotels/{}/window", "/api/hotels/{}/conflicts", "/api/hotels/{}/request", "/api/hotels/{}/sights",
              "/api/hotels/{}/web", "/api/hotels/{}/agent", "/api/hotels/{}/route?lat=43.6&lon=39.7", "/api/hotels/{}/nearby/cafe",
              "/api/hotelier/{}", "/api/hotelier/{}/questions", "/api/bookings/{}", "/api/profile/trips/{}",
              "/api/facts/{}", "/api/facts/{}/trace", "/api/characteristics/{}", "/api/sights/{}/photo.jpg"]:
        cases.append(("GET", p.format(e), None))
    cases.append(("POST", f"/api/hotels/{e}/ask", {"text": "вид на море?"}))
    cases.append(("POST", f"/api/hotelier/{e}/parse", {"text": "да"}))
    cases.append(("POST", "/api/compare", {"ids": [bid, H]}))
    cases.append(("POST", "/api/bookings", {"hotel_id": bid}))
# мусор в query
for p in [f"/api/hotels/{H}/window?facade=ZZ&floor=-999", f"/api/hotels/{H}/window?floor=abc", f"/api/hotels/{H}/window?floor=99999999999999999999",
          f"/api/hotels/{H}/day?month=13", f"/api/hotels/{H}/day?month=-1&interests=xx,yy&variant=999999&pins=a,b",
          f"/api/hotels/{H}/day/route?skip=" + q("1,2,<x>,💥"), f"/api/hotels/{H}/route?lat=999&lon=999",
          f"/api/hotels/{H}/route?lat=nan&lon=inf", f"/api/hotels/{H}/nearby/../../x", f"/api/hotels/{H}/web/search?q=" + q(LONG[:8000]),
          f"/api/hotels/{H}/sights?limit=-5", f"/api/hotels/{H}/sights?limit=100000", "/api/climate/rain?month=0",
          "/api/climate/rain?month=abc", f"/api/hotels/{H}/request?facade=<x>&floor=-3", "/api/hotels?limit=-1",
          "/assets/../../app/main.py", "/assets/%2e%2e/%2e%2e/app/main.py", "/..%2f..%2fetc%2fpasswd", "/api/../app/main.py"]:
    cases.append(("GET", p, None))
# мусор в теле
for t in WEIRD:
    cases += [("POST", "/api/describe", {"text": t}), ("POST", f"/api/hotels/{H}/ask", {"text": t}),
              ("POST", f"/api/hotelier/{H}/parse", {"text": t}), ("POST", f"/api/hotelier/{H}/parse", {"text": t, "topic": t}),
              ("POST", "/api/compare/custom", {"ids": [H, hs[1]["id"]], "text": t}),
              ("POST", "/api/characteristics/from-text", {"text": t}),
              ("POST", f"/api/hotelier/{H}/questions", {"text": t, "topic": t}),
              ("POST", f"/api/hotelier/{H}/conflicts/{q(t[:50] or 'x', safe='')}", {"action": t, "text": t}),
              ("POST", f"/api/hotelier/{H}/confirm", {"topic": t, "text": t}),
              ("POST", "/api/search", {"lenses": [t], "month": 99}), ("POST", "/api/trip/fit", {"interests": [t]})]
cases += [("POST", "/api/search", None, b"{not json"), ("POST", "/api/describe", None, b""), ("POST", "/api/compare", {"ids": []}),
          ("POST", "/api/compare", {"ids": [H] * 500}), ("POST", "/api/compare", {"ids": "x"}),
          ("POST", "/api/characteristics", {"spec": {"id": "../../evil", "kind": "x", "min_confidence": "abc"}}),
          ("POST", "/api/characteristics", {"spec": {"id": "zz_test", "min_confidence": "abc"}}),
          ("POST", "/api/characteristics", {"spec": {"id": "zz_test2", "ttl_days": "abc"}}),
          ("POST", "/api/characteristics", {"spec": []}),
          ("POST", "/api/bookings", {"hotel_id": H, "month": 99, "floor": -100, "facade": "<x>", "drop": ["x"] * 1000,
                                     "guests": {"adults": 1, "children": [-5, 300]}}),
          ("POST", "/api/bookings/xxx/feedback", {"answers": {"a": "<script>"}}),
          ("POST", "/api/profile/trips/xxx/review", {"stars": 9}),
          ("DELETE", "/api/characteristics/wifi", None), ("DELETE", "/api/characteristics/" + q("../../x", safe=""), None)]

bad = []
for c in cases:
    code, body = req(*c)
    if code == 500 or str(code).startswith("EXC") or (isinstance(code, int) and code >= 500):
        bad.append((code, c[0], c[1][:120], body[:200]))
    if c[1].startswith(("/assets", "/..", "/api/..")) and b"import" in body:
        bad.append(("LEAK", c[0], c[1], body[:120]))
print("cases:", len(cases), "bad:", len(bad))
seen = set()
for b in bad:
    k = (b[0], b[1], b[2].split("?")[0][:60])
    if k in seen:
        continue
    seen.add(k)
    print(b)
