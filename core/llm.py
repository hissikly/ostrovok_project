"""LLM-клиент: OpenAI-совместимый /chat/completions (LLM_* и запасной LLM_FALLBACK_* из .env).

Без ключа enabled() → False, и каждая фича работает в упрощённом режиме (правила).
Провайдеров два: основной и запасной. Основной не ответил — тот же запрос сразу уходит запасному.
Явный отказ (сеть, 5xx, 429, ключ) или два таймаута подряд выключают провайдера на COOLDOWN секунд,
чтобы гость не ждал таймаута на каждом запросе. Не ответили оба — chat() вернёт None, и фича ответит правилами.
LLM никогда не создаёт факты сама: только понимает текст и извлекает из него цитаты.
Только стандартная библиотека — без новых зависимостей рантайма.
"""
import json
import logging
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

from core.config import LLM_API_KEY, LLM_BASE_URL, LLM_FALLBACK, LLM_MODEL

log = logging.getLogger(__name__)
COOLDOWN = 60                    # с: сколько не трогать провайдера после отказа
CONNECT_TIMEOUT = 3              # с: не соединились за это время — хост лежит, не ждём полный таймаут ответа
_down: dict[str, float] = {}     # имя провайдера → до какого времени выключен
_fails: dict[str, int] = {}      # имя провайдера → отказов подряд


def _hard(e: Exception) -> bool:
    """Провайдер точно лежит: не достучались (DNS, соединение) или ответил 5xx / 429 / 401 / 403.
    Таймаут и кривой ответ — мягкий отказ: выключаем, только если он повторился."""
    if isinstance(e, urllib.error.HTTPError):
        return e.code >= 500 or e.code in (401, 403, 429)
    if isinstance(e, urllib.error.URLError):
        return not isinstance(e.reason, TimeoutError)
    return isinstance(e, Unreachable) or (isinstance(e, OSError) and not isinstance(e, TimeoutError))


def _providers() -> list[dict]:
    ps = [{"name": "main", "base": LLM_BASE_URL, "key": LLM_API_KEY, "model": LLM_MODEL},
          {"name": "fallback", **LLM_FALLBACK}]
    return [{**p, "base": p["base"] or "https://api.openai.com/v1"} for p in ps if p["key"] and p["model"]]


def enabled() -> bool:
    return bool(_providers())


def status() -> list[dict]:
    """Для /health: какие провайдеры настроены и не выключены ли сейчас (без ключей и адресов)."""
    return [{"name": p["name"], "up": _down.get(p["name"], 0) <= time.time()} for p in _providers()]


class Unreachable(OSError):
    """До провайдера не достучались за CONNECT_TIMEOUT — явный отказ."""


def _reach(base: str) -> None:
    """Быстрая проверка соединения: мёртвый хост ловим за 3 с, а не за 15–40 с таймаута ответа.
    Через прокси (HTTPS_PROXY) не проверяем — соединение идёт не напрямую."""
    u = urllib.parse.urlsplit(base)
    if u.scheme in urllib.request.getproxies():
        return
    try:
        socket.create_connection((u.hostname, u.port or (443 if u.scheme == "https" else 80)), CONNECT_TIMEOUT).close()
    except OSError as e:
        raise Unreachable(f"{type(e).__name__}") from e


def _post(p: dict, body: dict, timeout: int) -> dict:
    _reach(p["base"])
    req = urllib.request.Request(f"{p['base'].rstrip('/')}/chat/completions", data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {p['key']}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _ask(p: dict, body: dict, timeout: int) -> str:
    body = {**body, "model": p["model"]}
    try:
        data = _post(p, body, timeout)
    except urllib.error.HTTPError as e:
        if e.code != 400 or not ({"response_format", "reasoning"} & body.keys()):
            raise
        body.pop("response_format", None)      # не все совместимые API знают response_format и reasoning
        body.pop("reasoning", None)
        data = _post(p, body, timeout)
    return data["choices"][0]["message"]["content"]


def chat(messages: list[dict], *, as_json: bool = False, timeout: int = 40, temperature: float = 0,
         think: bool = True) -> str | dict | None:
    """Ответ модели текстом (или разобранный JSON при as_json); None — нет ключа или не ответил ни один провайдер.
    think=False — без «размышлений» (qwen и др. через OpenRouter-совместимый API): 1–3 с вместо 10–40 с."""
    body = {"messages": messages, "temperature": temperature}
    if as_json:
        body["response_format"] = {"type": "json_object"}
    if not think:
        body["reasoning"] = {"enabled": False}
    ps = _providers()
    live = [p for p in ps if _down.get(p["name"], 0) <= time.time()]
    text = None
    for p in live:
        try:
            text = _ask(p, body, timeout)
            _fails[p["name"]] = 0
            break
        except (urllib.error.URLError, TimeoutError, OSError, KeyError, IndexError, TypeError, ValueError) as e:
            n = _fails[p["name"]] = _fails.get(p["name"], 0) + 1
            if _hard(e) or n >= 2:      # один медленный ответ — не повод выключать провайдера для всех
                _down[p["name"]] = time.time() + COOLDOWN
            log.warning("LLM %s не ответила (%s %s), %s", p["name"], type(e).__name__, getattr(e, "code", ""),
                        "пробую запасную" if p is not live[-1] else "отвечаю правилами")
    if text is None or not as_json:
        return text
    m = re.search(r"\{.*\}", text, re.S)
    try:
        return json.loads(m.group(0)) if m else None
    except ValueError:
        return None
