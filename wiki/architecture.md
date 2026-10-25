---
title: Архитектура и структура репозитория
updated: 2026-10-25
sources: []
status: draft
---

# Архитектура

Правила работы агентов и людей — в `AGENTS.md` (корень репо). Продуктовая логика — [product-concept](product-concept.md) §5.

## Структура: одна фича = одна папка
Договорённость команды (24.10, просьба бэкендера) — см. [decisions](decisions.md).

```
features/<фича>/{README.md, backend/, pipeline/, frontend/}
core/    общее: гео-утилиты, LLM-клиент, БД, конфиг; walk.py — пешие маршруты по графу (beach_route, nearby)
app/     точка входа: роутеры фич, статика фронта, /health
data/    демо-данные (seed); большие файлы — скачиваются
```

Фичи (подробно — `features/README.md`):

| Слой | Фичи |
|---|---|
| Данные | `data_sources`, `hotels` |
| Ядро знаний | `facts`, `characteristics`, `conflicts` |
| Характеристики (считают факты) | `okno`, `beach_route`, `noise`, `nearby`, `climate` |
| Отельер | `hotelier` |
| Гость | `search`, `facade`, `day`, `compare`, `booking` |
| Качество | `metrics` |

## Модель факта (контракт для всех фич)
```text
Fact
  id
  hotel_id
  scope            "hotel" | "facade:W" | "floor_band:4-6" | "room_type:<id>"
  characteristic   id из реестра (features/characteristics/specs/*.yaml), напр. "sea_view"
  value            JSON: bool / number / enum / объект, напр. {"from_floor": 4, "share": 0.62}
  confidence       0..1 — из качества входных данных
  source           "computed:<tool>" | "osm" | "open-meteo" | "hotelier" | "card_mock" | "guest_feedback"
  method_version   напр. "horizon@0.1"
  evidence         JSON: параметры расчёта, id объектов OSM, текст ответа отельера
  obtained_at      ISO-дата
  valid_until      ISO-дата (срок годности по типу характеристики)
  status           "active" | "superseded" | "conflict" | "needs_review"
```

## API — соглашения
- Префикс `/api/`, JSON, ошибки — `{"error": "...", "detail": ...}`.
- Ответы с фактами всегда содержат `source`, `confidence`, `obtained_at`.
- Эндпоинты каждой фичи перечислены в её README; изменение — только с записью в `wiki/inbox.md`.
- `/health` → `{"status":"ok"}`.

## Поток данных
1. `data_sources` скачивает открытые данные → `data/`.
2. Фичи-характеристики в `pipeline/` считают факты офлайн → хранилище `facts`.
3. `conflicts` проверяет противоречия → `hotelier` задаёт вопросы → ответы становятся фактами.
4. Онлайн: `search` ранжирует по фактам, фичи гостя показывают их; LLM — только для понимания запроса и диалога с отельером.
