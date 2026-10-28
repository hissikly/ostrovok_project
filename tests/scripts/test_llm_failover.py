"""Переключение LLM-провайдеров (core/llm.py) на двух поддельных OpenAI-совместимых серверах.

Запуск из корня репозитория: python tests/scripts/test_llm_failover.py  (только стандартная библиотека).
Ключи не нужны и не тратятся: оба «провайдера» — локальные http-серверы, поведение задаём на лету.
"""
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MODE = {"main": "ok", "fallback": "ok"}     # ok | 500 | 429 | slow | garbage
HITS = {"main": 0, "fallback": 0}


def server(name):
    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            HITS[name] += 1
            self.rfile.read(int(self.headers["Content-Length"]))
            m = MODE[name]
            if m == "slow":
                time.sleep(2.5)
            if m in ("500", "429"):
                self.send_response(int(m)); self.end_headers(); return
            body = b"not json" if m == "garbage" else json.dumps(
                {"choices": [{"message": {"content": json.dumps({"by": name})}}]}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass
    s = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s.server_address[1]


pm, pf = server("main"), server("fallback")
os.environ.update(LLM_BASE_URL=f"http://127.0.0.1:{pm}/v1", LLM_API_KEY="k1", LLM_MODEL="m1",
                  LLM_FALLBACK_BASE_URL=f"http://127.0.0.1:{pf}/v1", LLM_FALLBACK_API_KEY="k2", LLM_FALLBACK_MODEL="m2")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core import llm  # noqa: E402

ok = True


def case(title, expect, timeout=1, **mode):
    global ok
    MODE.update(mode)
    t = time.time()
    r = llm.chat([{"role": "user", "content": "x"}], as_json=True, timeout=timeout)
    got = r["by"] if r else None
    passed = got == expect
    ok &= passed
    print(f"{'PASS' if passed else 'FAIL'}  {title:<62} ответ: {got or 'нет → правила':<14} {time.time() - t:4.1f} с  "
          f"статус: {', '.join(f'{p['name']}={'вкл' if p['up'] else 'выкл'}' for p in llm.status())}")


def reset():
    llm._down.clear(); llm._fails.clear()


case("1. Оба живы — отвечает основной", "main")
case("2. Основной 500 — тот же запрос отдаёт запасной", "fallback", main="500")
case("3. Основной выключен на 60 с — сразу запасной, без ожидания", "fallback")
reset()
case("4. Основной 429 (лимит) — запасной", "fallback", main="429")
reset()
case("5. Основной медленный (таймаут) — запасной; основной не выключен", "fallback", main="slow")
case("6. Второй таймаут подряд — запасной; основной выключен", "fallback")
case("   …дальше сразу запасной, без ожидания таймаута", "fallback")
reset()
case("7. Основной вернул мусор вместо JSON — запасной", "fallback", main="garbage")
reset()
case("8. Оба 500 — None, фича отвечает правилами", None, main="500", fallback="500")
case("9. Оба выключены — мгновенно None, без сетевых запросов", None)
llm._down = {k: 0 for k in llm._down}       # 60 с прошли
case("10. Остывание прошло, основной ожил — снова основной", "main", main="ok", fallback="ok")
reset()
llm.LLM_BASE_URL = "http://10.255.255.1/v1"    # адрес, где никто не отвечает: соединение висит
case("11. Хост основного не отвечает — запасной за ~3 с, основной выключен", "fallback", timeout=15)
case("   …следующий запрос сразу к запасному", "fallback", timeout=15)
print("ИТОГ:", "все проверки пройдены" if ok else "есть провалы")
sys.exit(0 if ok else 1)
