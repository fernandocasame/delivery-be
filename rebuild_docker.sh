#!/usr/bin/env bash
set -e

echo "=========================================="
echo "   Rebuilding Delivery Backend & Celery  "
echo "=========================================="

echo "[1/4] Running Django Migrations..."
if [ -f "./venv_linux/bin/python" ]; then
    ./venv_linux/bin/python manage.py migrate
elif command -v python3 &> /dev/null; then
    python3 manage.py migrate || true
fi

echo "[2/4] Cleaning existing standalone containers..."
docker rm -f delivery-backend delivery-redis delivery-celery-worker delivery-celery-beat || true

echo "[3/4] Building & Starting Docker Compose Services..."
docker compose down || true
docker compose up -d --build

echo "=========================================="
echo " Deployment Finished Successfully!        "
echo "=========================================="
docker compose ps
