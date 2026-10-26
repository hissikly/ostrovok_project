"""Обходит официальные сайты отелей (тег website в OSM) → data/raw/web/<hotel_id>.json.

Запуск (сеть, ~5–10 мин на все сайты; уже скачанные пропускаются):
    .venv/bin/python features/web_sources/pipeline/crawl.py [--only w201474333,w51764141] [--force | --retry]
Многие российские сайты не отвечают на зарубежные IP (обрыв TLS) — обходить без VPN.

Что берём: главную + до 10 страниц того же сайта, у которых в адресе или тексте ссылки есть
ключевые слова (номера, услуги, правила, вопросы, питомцы, парковка, питание, контакты…).
Вежливо: robots.txt, не чаще 1 запроса в секунду на сайт, таймаут, свой User-Agent.
Сохраняем только текст страницы (без HTML), адрес и время скачивания — это публичная
информация самого отеля, источник для фактов с дословной цитатой.
"""
import argparse
import datetime as dt
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

ROOT = Path(__file__).resolve().parents[3]
SEED, OUT = ROOT / "data/seed", ROOT / "data/raw/web"
UA = "OknoHackathonBot/0.1 (Ostrovok hackathon 2026 research prototype; reads public hotel pages)"
MAX_PAGES, DELAY, TIMEOUT = 10, 1.0, 12

# какие внутренние страницы стоит открыть: адрес или текст ссылки
KEYS = re.compile(
    r"номер|room|услуг|servic|правил|rule|polic|услови|faq|вопрос|о-нас|о нас|about|контакт|contact|"
    r"животн|питом|pet|парков|parking|питани|food|ресторан|restaurant|кафе|завтрак|breakfast|пляж|beach|"
    r"инфраструкт|infrastruct|дет|kids|child|трансфер|transfer|заезд|check|бассейн|pool|спа|spa|"
    r"проживан|accommodat|цен|price|тариф|информац|info|отел|hotel|сервис|удобств|amenit", re.I)
SKIP = re.compile(r"\.(jpe?g|png|gif|webp|svg|pdf|docx?|xlsx?|zip|rar|mp4|mp3|avi|ico|css|js)$|"
                  r"/(wp-admin|wp-login|cart|basket|login|auth|bitrix/|search|tel:|mailto:)|\?", re.I)
DROP = {"script", "style", "noscript", "svg", "head", "template", "iframe", "form", "select", "button"}
BLOCK = {"p", "div", "br", "li", "ul", "ol", "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6",
         "section", "article", "header", "footer", "table", "dd", "dt", "blockquote", "nav", "main"}


class Page(HTMLParser):
    """Текст страницы по блокам + ссылки; скрипты, стили и формы выбрасываем."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.links, self.title = [], [], ""
        self._drop, self._in_title, self._a = 0, False, None

    def handle_starttag(self, tag, attrs):
        if tag in DROP:
            self._drop += 1
        if tag == "title":
            self._in_title = True
        if tag in BLOCK:
            self.parts.append("\n")
        if tag == "a":
            href = dict(attrs).get("href")
            self._a = [href, ""] if href else None

    def handle_endtag(self, tag):
        if tag in DROP and self._drop:
            self._drop -= 1
        if tag == "title":
            self._in_title = False
        if tag in BLOCK:
            self.parts.append("\n")
        if tag == "a" and self._a:
            self.links.append(tuple(self._a))
            self._a = None

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._drop:
            return
        self.parts.append(data)
        if self._a:
            self._a[1] += data

    def text(self) -> str:
        raw = "".join(self.parts)
        lines = [re.sub(r"[ \t ]+", " ", ln).strip() for ln in raw.split("\n")]
        out, prev = [], None
        for ln in lines:
            if ln and ln != prev:
                out.append(ln)
            prev = ln
        return "\n".join(out)


# сайт сети отелей: страница конкретного отеля в глубине пути, рядом — другие города сети
CITIES = re.compile(r"moscow|moskva|saint-petersburg|spb|peterburg|kazan|kaliningrad|krasnodar|anapa|gelendzhik|"
                    r"novorossiysk|yalta|sevastopol|kislovodsk|altai|altay|murmansk|samara|ufa|perm|tyumen|"
                    r"vladivostok|novosibirsk|ekaterinburg|yekaterinburg|nizhny|rostov|voronezh|omsk|irkutsk|"
                    r"repino|zelenogorsk|petrozavodsk|astana|almaty|minsk|baku|tbilisi|dubai|turkey", re.I)
GENERIC = {"ru", "en", "hotel", "hotels", "otel", "sochi", "index", "html", "php", "www", "spa", "resort", "and", "the"}


def slug_words(url: str) -> set[str]:
    """Отличительные слова из пути главной (azimut-hotel-vinogradnaya-sochi → {azimut, vinogradnaya})."""
    segs = [x for x in urlparse(url).path.split("/") if x]
    return {w for w in re.split(r"[-_.]", segs[-1].lower()) if len(w) > 3 and w not in GENERIC} if segs else set()


def host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def get(sess, url):
    r = sess.get(url, timeout=TIMEOUT, allow_redirects=True)
    if r.status_code != 200 or "html" not in r.headers.get("content-type", "html"):
        return None, r.status_code
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding
    return r, 200


def robots(sess, base):
    rp = RobotFileParser()
    try:
        r = sess.get(urljoin(base, "/robots.txt"), timeout=TIMEOUT)
        rp.parse(r.text.splitlines() if r.status_code == 200 else [])
    except requests.RequestException:
        rp.parse([])
    return rp


def crawl(hotel: dict) -> dict:
    site = hotel["website"].strip()
    if not site.startswith("http"):
        site = "http://" + site
    site = re.sub(r"\?utm_[^#]*$", "", site)
    now = lambda: dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")  # noqa: E731
    res = {"hotel_id": hotel["id"], "name": hotel["name"], "website": site, "pages": [], "status": "ok"}
    sess = requests.Session()
    sess.headers.update({"User-Agent": UA, "Accept-Language": "ru,en;q=0.5"})
    try:
        rp = robots(sess, site)
        if not rp.can_fetch(UA, site):
            return {**res, "status": "robots_disallow"}
        r, code = get(sess, site)
        if r is None:
            return {**res, "status": f"http_{code}"}
        dom, own = host(r.url), slug_words(r.url)
        queue, seen = [r.url], {urldefrag(r.url)[0].rstrip("/")}
        first = r
        while queue and len(res["pages"]) < MAX_PAGES + 1:
            url = queue.pop(0)
            home = first is not None
            if home:
                r, first = first, None
            else:
                time.sleep(DELAY)
                if not rp.can_fetch(UA, url):
                    continue
                try:
                    r, _ = get(sess, url)
                except requests.RequestException:
                    continue
                if r is None:
                    continue
            p = Page()
            try:
                p.feed(r.text)
            except Exception:  # битая разметка — берём что успели
                pass
            text = p.text()
            if len(text) > 80 and all(x["text"] != text[:60000] for x in res["pages"]):
                res["pages"].append({"url": r.url, "title": p.title.strip()[:200], "text": text[:60000],
                                     "fetched_at": now()})
            if home:                                   # ссылки берём только с главной
                cand = []
                for href, label in p.links:
                    u = urldefrag(urljoin(r.url, href.strip()))[0]
                    if not u.startswith("http") or host(u) != dom or SKIP.search(u):
                        continue
                    key = u.rstrip("/")
                    if key in seen:
                        continue
                    seen.add(key)
                    if CITIES.search(urlparse(u).path):          # другой отель сети
                        continue
                    score = len(KEYS.findall(u)) * 2 + len(KEYS.findall(label or ""))
                    if own and any(w in u.lower() for w in own):  # страница именно этого отеля
                        score += 4
                    if score:
                        cand.append((-score, len(u), u))
                queue += [u for _, _, u in sorted(cand)[:MAX_PAGES]]
    except requests.exceptions.SSLError:
        res["status"] = "ssl_error"
    except requests.RequestException as e:
        res["status"] = "error:" + type(e).__name__
    if not res["pages"] and res["status"] == "ok":
        res["status"] = "empty"
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--retry", action="store_true", help="повторить сайты, которые не ответили")
    ap.add_argument("--workers", type=int, default=24)
    a = ap.parse_args()
    hotels = [h for h in json.load(open(SEED / "hotels.json", encoding="utf-8")) if h.get("website")]
    if a.only:
        hotels = [h for h in hotels if h["id"] in a.only.split(",")]
    OUT.mkdir(parents=True, exist_ok=True)
    def need(h):
        p = OUT / f"{h['id']}.json"
        return a.force or not p.exists() or (a.retry and json.load(open(p, encoding="utf-8"))["status"] != "ok")
    todo = [h for h in hotels if need(h)]
    print(f"сайтов {len(hotels)}, скачать {len(todo)}", flush=True)

    def one(h):
        res = crawl(h)
        json.dump(res, open(OUT / f"{h['id']}.json", "w", encoding="utf-8"), ensure_ascii=False)
        print(f"{h['id']:>12} {res['status']:<16} {len(res['pages']):>2} стр  {res['website']}", flush=True)
        return res

    with ThreadPoolExecutor(a.workers) as ex:
        list(ex.map(one, todo))
    stats = {}
    for p in OUT.glob("*.json"):
        if p.name.startswith("_"):
            continue
        s = json.load(open(p, encoding="utf-8"))["status"]
        stats[s] = stats.get(s, 0) + 1
    print(json.dumps(stats, ensure_ascii=False), file=sys.stderr)


if __name__ == "__main__":
    main()
