#!/bin/sh
# Локальная проверка: собрать демо-данные, фронт и поднять сервис без Docker.
# Порт: PORT=8090 sh tools/dev_check.sh  (по умолчанию 8080)
# Полный пересчёт «О!кна» (минуты): .venv/bin/python features/okno/pipeline/compute_all.py --force
set -e
cd "$(dirname "$0")/.."
.venv/bin/python features/hotels/pipeline/build_hotels.py
.venv/bin/python features/beach_route/pipeline/beach_distance.py
.venv/bin/python features/nearby/pipeline/export_poi.py
# пешеходный граф: только если скачана выгрузка OSM (см. features/data_sources/pipeline/extract_walk_pbf.py)
if [ -f data/raw/osm/south-fed-district.osm.pbf ]; then
  .venv/bin/python features/data_sources/pipeline/extract_walk_pbf.py
  .venv/bin/python features/noise/pipeline/extract_sources.py
fi
[ -f data/raw/noise_sources.json ] && .venv/bin/python features/noise/pipeline/noise.py
if [ -d data/raw/walk ]; then
  .venv/bin/python features/beach_route/pipeline/build_walk_graph.py
  .venv/bin/python features/beach_route/pipeline/beach_route.py
  .venv/bin/python features/nearby/pipeline/walk_times.py
fi
.venv/bin/python features/okno/pipeline/compute_all.py
.venv/bin/python features/okno/pipeline/export_seed.py
.venv/bin/python features/day/pipeline/morning_sun.py
[ -f data/raw/osm_poi.json ] && .venv/bin/python features/day/pipeline/morning_cafes.py
du -sh data/seed
uv pip install -q -p .venv -r app/requirements.txt
npm install --no-audit --no-fund
npm run build
exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "${PORT:-8080}"
