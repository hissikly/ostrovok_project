#!/bin/sh
# Локальная проверка: собрать демо-данные, фронт и поднять сервис без Docker.
# Порт: PORT=8090 sh tools/dev_check.sh  (по умолчанию 8080)
# Полный пересчёт «О!кна» (минуты): .venv/bin/python features/okno/pipeline/compute_all.py --force
set -e
cd "$(dirname "$0")/.."
.venv/bin/python features/hotels/pipeline/build_hotels.py
.venv/bin/python features/okno/pipeline/compute_all.py
.venv/bin/python features/okno/pipeline/export_seed.py
du -sh data/seed
uv pip install -q -p .venv -r app/requirements.txt
npm install --no-audit --no-fund
npm run build
exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "${PORT:-8080}"
