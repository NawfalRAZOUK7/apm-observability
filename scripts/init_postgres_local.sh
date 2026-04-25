#!/bin/bash

# PostgreSQL 17 Local Initialization Script

set -e

echo "Initializing PostgreSQL 17 locally..."

# Initialize data directory if not exists
if [ ! -d "/opt/homebrew/var/postgresql@17" ]; then
    echo "Creating data directory..."
    initdb /opt/homebrew/var/postgresql@17
fi

# Start PostgreSQL service
echo "Starting PostgreSQL service..."
brew services start postgresql@17 || brew services restart postgresql@17

# Wait for service to be ready
sleep 5

# Create superuser (postgres) if not exists
echo "Creating superuser..."
psql -d postgres -c "CREATE USER postgres SUPERUSER CREATEDB CREATEROLE;" 2>/dev/null || echo "Superuser 'postgres' already exists or creation failed"

# Create database and user
echo "Creating database and user..."
createdb apm || echo "Database 'apm' already exists"
createuser apm -s || echo "User 'apm' already exists"

# Set password
psql -d postgres -c "ALTER USER apm PASSWORD 'apm';" || echo "Password already set"

# Grant permissions
psql -d postgres -c "GRANT ALL PRIVILEGES ON DATABASE apm TO apm;" || echo "Permissions already granted"

# Enable TimescaleDB extension
psql -U apm -d apm -c "CREATE EXTENSION IF NOT EXISTS timescaledb;" || echo "TimescaleDB already enabled"

echo "PostgreSQL 17 initialization complete!"
echo "Superuser: postgres"
echo "Database: apm"
echo "User: apm"
echo "Password: apm"