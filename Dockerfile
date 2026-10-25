# --- 1. сборка фронта ---
FROM --platform=linux/amd64 node:20.18.1-alpine AS web
WORKDIR /src
COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi
COPY vite.config.js ./
COPY app/frontend app/frontend
COPY features features
RUN npm run build

# --- 2. рантайм: только Python и готовые данные, без dev-инструментов ---
FROM --platform=linux/amd64 python:3.12.8-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_PORT=8080
WORKDIR /app
COPY app/requirements.txt app/requirements.txt
RUN pip install --no-cache-dir -r app/requirements.txt
COPY core core
COPY features features
COPY app/main.py app/__init__.py app/
COPY data/seed data/seed
COPY --from=web /src/app/static app/static
RUN useradd --create-home --uid 10001 okno && chown -R okno /app
USER okno
EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${APP_PORT}"]
