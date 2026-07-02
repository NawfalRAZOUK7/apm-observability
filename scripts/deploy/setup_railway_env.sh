#!/bin/bash
# Railway Environment Setup Script

echo "=== Setting up Railway Environment Variables ==="
echo ""

# Django Configuration
railway variables set DJANGO_DEBUG=0
railway variables set DJANGO_SECRET_KEY="$(openssl rand -hex 32)"
railway variables set DJANGO_ALLOWED_HOSTS="${RAILWAY_STATIC_URL:-*}"
railway variables set DJANGO_TIME_ZONE=UTC

# Database Configuration (Railway will provide these automatically when you add PostgreSQL)
echo "Note: Database variables will be set automatically when you add PostgreSQL service"
echo "Expected variables:"
echo "  POSTGRES_HOST=\${{Postgres.POSTGRES_HOST}}"
echo "  POSTGRES_PORT=\${{Postgres.POSTGRES_PORT}}"
echo "  POSTGRES_DB=\${{Postgres.POSTGRES_DB}}"
echo "  POSTGRES_USER=\${{Postgres.POSTGRES_USER}}"
echo "  POSTGRES_PASSWORD=\${{Postgres.POSTGRES_PASSWORD}}"

# Database SSL
railway variables set DB_SSLMODE=require
railway variables set DB_CONN_MAX_AGE=60

# Gunicorn Configuration (optimized for Railway's 512MB limit)
railway variables set GUNICORN_WORKERS=2
railway variables set GUNICORN_TIMEOUT=30
railway variables set GUNICORN_BIND=0.0.0.0:\${PORT:-8000}

# Environment
railway variables set ENVIRONMENT=production

echo ""
echo "✅ Environment variables set!"
echo ""
echo "Next steps:"
echo "1. Add PostgreSQL database: railway add → Database → PostgreSQL"
echo "2. Enable TimescaleDB: railway connect postgres → CREATE EXTENSION timescaledb;"
echo "3. Redeploy: railway up"
echo ""
