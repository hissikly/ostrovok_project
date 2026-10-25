"""База знаний по уровням. Публичный интерфейс: ask(hotel_id, text, ctx), resolve(hotel_id, topic, ctx),
faq(hotel_id, ctx), topics(); запись ответов — store.write(path, topic, …), путь отеля — store.hotel_path(id)."""
from features.knowledge.backend.answers import ask, faq, resolve, topics  # noqa: F401
from features.knowledge.backend.store import hotel_path, write  # noqa: F401
