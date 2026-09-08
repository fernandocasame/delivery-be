#!/usr/bin/env bash
set -e

echo "=========================================="
echo "   Rebuilding Delivery Backend & Celery  "
echo "=========================================="

# Detect docker compose / docker-compose command
if docker compose version &>/dev/null; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &>/dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo "ERROR: Docker Compose is not installed on this system."
    echo "Please install Docker Compose by executing:"
    echo "  sudo apt update && sudo apt install -y docker-compose-v2"
    exit 1
fi

echo "[1/4] Running Django Migrations..."
if [ -f "./venv_linux/bin/python" ]; then
    ./venv_linux/bin/python manage.py migrate
elif command -v python3 &> /dev/null; then
    python3 manage.py migrate || true
fi

echo "[2/4] Cleaning existing standalone containers..."
docker rm -f delivery-backend delivery-redis delivery-celery-worker delivery-celery-beat 2>/dev/null || true

echo "[3/4] Building & Starting Docker Compose Services..."
$COMPOSE_CMD down 2>/dev/null || true
$COMPOSE_CMD up -d --build

echo "=========================================="
echo " Deployment Finished Successfully!        "
echo "=========================================="
$COMPOSE_CMD ps
