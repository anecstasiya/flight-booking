#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

docker compose up --build -d --wait --wait-timeout 240
docker compose exec -T booking-service python - booking < scripts/check_database.py
docker compose exec -T flight-service python - flight < scripts/check_database.py
docker compose exec -T booking-service python -c \
  "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').read().decode())"
docker compose exec -T flight-service python -m app.healthcheck
printf 'All checks passed. Services are still running.\n'
