#!/bin/bash
# SQLGuardian - Dev Bootstrap Script
# Run this once to spin everything up from scratch.

set -e

echo "======================================"
echo "  SQLGuardian - Dev Environment Setup"
echo "======================================"

# 1. Copy .env if it doesn't exist
if [ ! -f .env ]; then
    cp .env.example .env
    echo "[OK] Created .env from .env.example"
else
    echo "[SKIP] .env already exists"
fi

# 2. Create logs dir
mkdir -p logs
echo "[OK] logs/ directory ready"

# 3. Start containers
echo ""
echo "Starting Docker containers..."
docker compose up -d --build

# 4. Wait for SQL Server to be healthy
echo ""
echo "Waiting for SQL Server to be healthy..."
for i in {1..30}; do
    STATUS=$(docker inspect --format='{{.State.Health.Status}}' sqlguardian-sqlserver 2>/dev/null || echo "starting")
    if [ "$STATUS" = "healthy" ]; then
        echo "[OK] SQL Server is healthy"
        break
    fi
    echo "  Attempt $i/30 - status: $STATUS"
    sleep 5
done

# 5. Run seed script
echo ""
echo "Running seed script..."
docker exec sqlguardian-sqlserver /opt/mssql-tools18/bin/sqlcmd \
    -S localhost \
    -U sa \
    -P "SQLGuardian@2024" \
    -i /scripts/seed_dev.sql \
    -No \
    && echo "[OK] Seed script complete" \
    || echo "[WARN] Seed script had errors (may already be seeded)"

echo ""
echo "======================================"
echo "  SQLGuardian is running!"
echo ""
echo "  API:       http://localhost:8000"
echo "  API Docs:  http://localhost:8000/docs"
echo "  Dashboard: http://localhost:8501"
echo "======================================"
