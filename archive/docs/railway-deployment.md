# Railway Deployment Configuration

## Files needed for Railway deployment:

### 1. railway.json (Railway configuration)

```json
{
  "build": {
    "builder": "dockerfile"
  },
  "deploy": {
    "startCommand": "bash docker/entrypoint.sh"
  }
}
```

### 2. Dockerfile.railway (Railway-specific Dockerfile)

```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Create non-root user
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Expose port
EXPOSE 8000

# Run the application
CMD ["bash", "docker/entrypoint.sh"]
```

### 3. Environment Variables for Railway:

```
# Django Configuration
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=your-super-secret-key-here-make-it-long-and-random
DJANGO_ALLOWED_HOSTS=${{RAILWAY_STATIC_URL}}
DJANGO_TIME_ZONE=UTC

# Database (Railway will provide these automatically)
POSTGRES_HOST=${{Postgres.POSTGRES_HOST}}
POSTGRES_PORT=${{Postgres.POSTGRES_PORT}}
POSTGRES_DB=${{Postgres.POSTGRES_DB}}
POSTGRES_USER=${{Postgres.POSTGRES_USER}}
POSTGRES_PASSWORD=${{Postgres.POSTGRES_PASSWORD}}

# Database SSL
DB_SSLMODE=require
DB_CONN_MAX_AGE=60

# Gunicorn Configuration
GUNICORN_WORKERS=2
GUNICORN_TIMEOUT=30
GUNICORN_BIND=0.0.0.0:8000

# Environment
ENVIRONMENT=production

# Optional: MinIO Configuration (if using Railway volumes)
MINIO_ENDPOINT=${{RAILWAY_STATIC_URL}}
MINIO_ACCESS_KEY=your-minio-key
MINIO_SECRET_KEY=your-minio-secret
```

### 4. railway.toml (Alternative configuration)

```toml
[build]
builder = "dockerfile"

[deploy]
startCommand = "bash docker/entrypoint.sh"
healthcheckPath = "/api/health/"
healthcheckTimeout = 300
restartPolicyType = "ON_FAILURE"
```

## Deployment Steps:

1. **Create Railway account** at [railway.app](https://railway.app)
2. **Connect GitHub repository**
3. **Railway will auto-detect Docker setup**
4. **Add PostgreSQL database** (Railway provides this)
5. **Set environment variables** (see above)
6. **Deploy!**

## Railway-specific Optimizations:

- **Reduced Gunicorn workers** (2 instead of 3) for 512MB RAM limit
- **Shorter timeouts** to fit within Railway's limits
- **SSL mode=require** for Railway's managed PostgreSQL
- **Automatic HTTPS** provided by Railway

## Testing Railway Deployment:

After deployment, test these endpoints:

- Health check: `GET https://your-app.railway.app/api/health/`
- API docs: `GET https://your-app.railway.app/api/docs/`
- Database test: `GET https://your-app.railway.app/api/health/?db=1`

Railway will provide the URL automatically after deployment!</content>
<parameter name="filePath">/Users/nawfalrazouk/apm-observability/railway-deployment.md
