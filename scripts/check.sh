#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

docker compose up --build -d --wait --wait-timeout 240
for service in booking-service flight-service; do
  docker compose exec -T "$service" alembic upgrade head
  docker compose exec -T "$service" alembic check
done
trap 'docker compose start redis-master redis-replica flight-service >/dev/null' EXIT
docker compose --profile test run --build --rm tests
docker compose stop flight-service
docker compose --profile test run --no-deps --rm tests python tests/check_outage.py down
docker compose start flight-service
docker compose --profile test run --no-deps --rm tests python tests/check_outage.py up
