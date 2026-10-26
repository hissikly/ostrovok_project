"""LLM-клиент: OpenAI-совместимый /chat/completions (LLM_BASE_URL, LLM_API_KEY, LLM_MODEL из .env).

Без ключа enabled() → False, и каждая фича работает в упрощённом режиме (правила).
LLM никогда не создаёт факты сама: только понимает текст и извлекает из него цитаты.
Только стандартная библиотека — без новых зависимостей рантайма.
"""
import json
import logging
import re
import urllib.error
import urllib.request

from core.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

log = logging.getLogger(__name__)


def enabled() -> bool:
    return bool(LLM_API_KEY and LLM_MODEL)


def _post(body: dict, timeout: int) -> dict:
    base = (LLM_BASE_URL or "https://api.openai.com/v1").rstrip("/")
    req = urllib.request.Request(f"{base}/chat/completions", data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def chat(messages: list[dict], *, as_json: bool = False, timeout: int = 40, temperature: float = 0) -> str | dict | None:
    """Ответ модели текстом (или разобранный JSON при as_json); None — нет ключа или ошибка."""
    if not enabled():
        return None
    body = {"model": LLM_MODEL, "messages": messages, "temperature": temperature}
    if as_json:
        body["response_format"] = {"type": "json_object"}
    try:
        try:
            data = _post(body, timeout)
        except urllib.error.HTTPError as e:
            if e.code != 400 or "response_format" not in body:
                raise
            body.pop("response_format")            # не все совместимые API знают response_format
            data = _post(body, timeout)
        text = data["choices"][0]["message"]["content"]
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as e:
        log.warning("LLM недоступна: %s", e)
        return None
    if not as_json:
        return text
    m = re.search(r"\{.*\}", text, re.S)
    try:
        return json.loads(m.group(0)) if m else None
    except ValueError:
        return None
