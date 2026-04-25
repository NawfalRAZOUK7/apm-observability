#!/bin/bash
# Check Railway Database Setup

echo "=== Checking Railway Database Setup ==="
echo ""

# Check if database variables are available
echo "Checking database connection variables..."
railway variables | grep -E "(POSTGRES|DATABASE_URL)" || echo "No database variables found yet"

echo ""
echo "If you see database variables above, the database is connected!"
echo "If not, make sure you've added PostgreSQL service first."
echo ""

# Show next steps
echo "=== Next Steps ==="
echo "1. ✅ Add PostgreSQL database (if not done)"
echo "2. Run: ./setup_railway_env.sh"
echo "3. Enable TimescaleDB: railway connect postgres"
echo "4. Run SQL: CREATE EXTENSION IF NOT EXISTS timescaledb;"
echo "5. Redeploy: railway up"
echo "6. Test: railway open"
echo ""