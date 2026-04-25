# Dockerfile
FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System deps (psycopg needs libpq; build tools are minimal and safe)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for better layer caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the Django project
COPY . /app

# Where collectstatic will put files (WhiteNoise serves from here)
RUN mkdir -p /app/staticfiles

# Create a non-root user for security
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Default command (entrypoint.sh in TODO #4 can later run migrate/collectstatic before this)
CMD ["gunicorn", "apm_platform.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60"]
