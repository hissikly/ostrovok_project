"""Тексты сайтов отелей → чанки для поиска: data/raw/web/*.json → data/seed/web_chunks.json.gz.

Запуск: .venv/bin/python features/web_sources/pipeline/index.py

Строки, повторяющиеся на нескольких страницах сайта (меню, подвал), оставляем только на главной.
Чанк — ~600 символов целыми строками, соседние чанки перекрываются одной строкой.
Страницы отзывов индексируем, но помечаем (это слова гостей, а не отеля).
"""
import gzip
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RAW, SEED = ROOT / "data/raw/web", ROOT / "data/seed"
SIZE, MAX_PER_HOTEL = 600, 160
REVIEWS = re.compile(r"otzyv|otziv|review|отзыв|guestbook|gostevaya", re.I)


def chunks(lines: list[str]) -> list[str]:
    out, cur = [], []
    for ln in lines:
        while len(ln) > SIZE:                       # длинный абзац режем по предложениям
            cut = ln.rfind(". ", 0, SIZE)
            cut = cut + 1 if cut > SIZE // 3 else SIZE
            lines_head, ln = ln[:cut].strip(), ln[cut:].strip()
            if cur:
                out.append("\n".join(cur))
                cur = []
            out.append(lines_head)
        if cur and sum(len(x) + 1 for x in cur) + len(ln) > SIZE:
            out.append("\n".join(cur))
            cur = cur[-1:] if len(cur[-1]) < SIZE // 3 else []
        if ln:
            cur.append(ln)
    if cur:
        out.append("\n".join(cur))
    return [c for c in out if len(c) >= 40]


def site_chunks(site: dict) -> list[dict]:
    pages = site["pages"]
    seen = Counter(ln for p in pages for ln in set(p["text"].split("\n")))
    rep = {ln for ln, n in seen.items() if n >= 3 and len(pages) >= 3}
    out, dup = [], set()
    for i, p in enumerate(pages):
        lines = [ln for ln in p["text"].split("\n") if i == 0 or ln not in rep]
        for c in chunks(lines):
            if c in dup:
                continue
            dup.add(c)
            out.append({"url": p["url"], "title": p["title"], "text": c, "fetched_at": p["fetched_at"],
                        "reviews": bool(REVIEWS.search(p["url"]))})
    return out[:MAX_PER_HOTEL]


def main():
    sites, all_chunks, stats = [], [], Counter()
    for path in sorted(p for p in RAW.glob("*.json") if not p.name.startswith("_")):   # _llm_cache и отчёты
        s = json.load(open(path, encoding="utf-8"))
        stats[s["status"]] += 1
        cs = site_chunks(s) if s["pages"] else []
        sites.append({"hotel_id": s["hotel_id"], "website": s["website"], "status": s["status"],
                      "pages": len(s["pages"]), "chunks": len(cs),
                      "fetched_at": s["pages"][0]["fetched_at"] if s["pages"] else None})
        all_chunks += [{"id": f"{s['hotel_id']}:{i}", "hotel_id": s["hotel_id"], **c} for i, c in enumerate(cs)]
    with gzip.open(SEED / "web_chunks.json.gz", "wt", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, separators=(",", ":"))
    json.dump({"sites": sites, "stats": dict(stats)}, open(SEED / "web_sites.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    size = (SEED / "web_chunks.json.gz").stat().st_size
    print(f"сайтов {len(sites)} ({dict(stats)}), с текстом {sum(1 for s in sites if s['chunks'])}, "
          f"чанков {len(all_chunks)}, {size / 1e6:.1f} МБ")


if __name__ == "__main__":
    main()
