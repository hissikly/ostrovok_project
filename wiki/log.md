---
title: Лог
updated: 2026-10-24
sources: []
status: agreed
---

# Лог

- 2026-10-24 · ingest · Заметки команды (PDF со слайдами) и общий чат · raw/slides/*
- 2026-10-24 · ingest · Описания треков, правила по технике, контрольные точки с docs.ostrovok.tech · raw/organizers/*, requirements.md
- 2026-10-24 · ingest · Чат трека 2: уточнения Ilia Marashli (суть не в DS, фундамент, свобода флоу), ответы Timur Firsakov · raw/chat/2026-10-24-chats.md, requirements.md, open-questions.md
- 2026-10-24 · update · Концепция v1 (чат-поиск) отклонена пользователем → концепция v2 «О!кно» (3D-город, линзы, «Окно», фасад, «Твой день») · product-concept.md, decisions.md
- 2026-10-24 · ingest · Стиль Островка: 261 CSS-переменная с ostrovok.ru, публикации о ребрендинге 2024 · raw/brand/ostrovok-css-tokens.txt, design-system.md
- 2026-10-24 · update · Развёрнута LLM wiki: схема в CLAUDE.md, index, log, decisions, open-questions · все страницы
- 2026-10-24 · update · Макет «Окна» в стиле Островка · mockups/okno.html
- 2026-10-24 · query · Как работает «вид из окна»: данные, расчёт профилей горизонта, реальное время; развёртка 160° признана непонятной · window-view-method.md, index.md
- 2026-10-24 · decision · «ИИ-завод» с агентом в Cursor отложен · decisions.md
- 2026-10-24 · update · Схема пользовательского пути в Obsidian canvas: 7 этапов × дорожки гость/система/отельер, легенда цветов, привязка к задачам трека · index.md, tools/make_journey_canvas.py
- 2026-10-24 · ingest · Чат трека вечер 24.10: обязателен только «Ожидаемый результат», задачи — опорные; критерии не опубликуют; важны релевантность, доверие, влияние на решение · raw/chat/2026-10-24-evening-track2.md, requirements.md, open-questions.md, product-concept.md (§3.5), decisions.md, canvas (+2 карточки)
- 2026-10-24 · decision · Пользователь одобрил «главное — первым», калибровку и «было / стало» · decisions.md
- 2026-10-24 · query · Что должно быть в итоговом решении — чек-лист сдачи · deliverables.md, index.md
- 2026-10-24 · update · Подготовка к совместной работе с бэкендером: AGENTS.md, правило Cursor, 17 папок фич с README, architecture.md, inbox.md; пуш в GitHub · AGENTS.md, CLAUDE.md, features/*, architecture.md, inbox.md, decisions.md, index.md
- 2026-10-24 · update · Спайк данных Сочи: OSM (92 тыс. зданий, этажность 37%, 209 отелей с контуром), DEM Copernicus, профили горизонта Pullman и Azimut, конусы обзора на карте; найдены подвох DSM и ошибка времени заката в макете · data-check-sochi.md, open-questions.md, index.md
- 2026-10-25 · update · Баг: пропадали скруглённые фасады (восток Pullman) — исправлено суммированием коротких рёбер · data-check-sochi.md
- 2026-10-25 · decision · Убраны зоны «фронт/бэкенд» из AGENTS.md и CLAUDE.md: оба работают над всем, правило — фича в своей папке · decisions.md
- 2026-10-25 · update · Сервис v0: FastAPI (/health, /api/hotels, /api/hotels/{id}/facts, /api/hotels/{id}/window), фронт React+MapLibre в стиле Островка, Dockerfile/compose (не проверены); демо-данные 718 объектов + факт высоты по DEM + «О!кно» для 2 отелей; исправлена высота 0 м у прибрежных отелей; проверено в браузере на :8080 · index.md, features/{hotels,facts,okno}/README.md
- 2026-10-25 · update · Редизайн по скринам приложения Островка: белые блоки на сером, зелёный рейтинг, строки с иконками, «О!кно» словами + салатовая плашка заката, «Что важно знать» с уверенностью словами; убраны техтекст, легенда, кольца, лучи в склоны; ссылки на отель #id · design-system.md, features/{hotels,facts,okno}/frontend
- 2026-10-25 · update · Убраны разделители «·» по всему интерфейсу (пользователь: «нейрослоп»): шапка — логотип + салатовый чип «О!кно», поездка — сегменты с иконками; факты по сторонам — строками «Окна на запад — с любого этажа» · design-system.md
