---
title: Индекс wiki
updated: 2026-10-24
sources: []
status: agreed
---

# Wiki проекта «О!кно»

Хакатон Островка 2026, трек 2 «О!дин шаг до идеального отеля». Сдача — **29.10 до 10:00 МСК**.

**Состояние (25.10):** сервис v0 работает локально — `sh tools/dev_check.sh` → http://localhost:8080: карта 718 объектов Сочи, карточка отеля в стиле Островка, факты с источником/уверенностью/датой, «О!кно» с лучами обзора для Pullman и Azimut. Docker-сборка написана, но ещё не проверена.

## Страницы
| Страница | О чём |
|---|---|
| [deliverables.md](deliverables.md) | **Что должно быть в итоговом решении**: чек-лист сдачи (формальное / обязательное / сильное) |
| [architecture.md](architecture.md) | Структура репо (одна фича = одна папка), модель факта, соглашения API, поток данных |
| [requirements.md](requirements.md) | Что требуют организаторы: задачи трека, правила сдачи, сроки |
| [product-concept.md](product-concept.md) | Концепция v2: 3D-город, линзы, «Окно», фасад, «Твой день», отельер; архитектура, приоритеты, план по дням, сценарий видео |
| [window-view-method.md](window-view-method.md) | Как считается «вид из окна»: данные, офлайн-расчёт профиля горизонта, отрисовка, ограничения |
| [data-check-sochi.md](data-check-sochi.md) | Проверка данных по Сочи: полнота OSM, подвохи карты высот, первые реальные «виды из окна» (Pullman, Azimut) |
| [design-system.md](design-system.md) | Стиль Островка: цвета и токены с сайта, радиусы, шрифт-замена, иконки, айдентика «О!» |
| [decisions.md](decisions.md) | Журнал решений команды |
| [open-questions.md](open-questions.md) | Вопросы к организаторам и внутри команды |
| [inbox.md](inbox.md) | Входящие от бэкендера и его агента — переносятся в wiki |
| [log.md](log.md) | Хронология работы с wiki |

## Схемы и макеты
- [user-journey.canvas](user-journey.canvas) — схема пользовательского пути (Obsidian canvas; оригинал в хранилище Obsidian), генерируется `tools/make_journey_canvas.py`
- `../features/README.md` — список фич и их папок
- [../mockups/okno.html](../mockups/okno.html) — карточка отеля с фичей «Окно» в стиле Островка

- `mockups/spike-cone-pullman.html`, `mockups/spike-cone-azimut.html` — конус обзора на реальных данных

## Источники (`raw/`)
- `raw/organizers/` — описания треков, правила по технике, контрольные точки (скачаны с docs.ostrovok.tech 24.10)
- `raw/chat/` — выдержки из чатов хакатона
- `raw/slides/` — слайды с открытия и заметки команды (PDF)
- `raw/brand/` — CSS-токены, извлечённые с ostrovok.ru
