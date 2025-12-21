# Railway Deployment Guide - Complete Steps

## 🎯 **Railway Free Deployment - Complete Guide**

This guide covers deploying your APM Observability Django + TimescaleDB application to Railway (completely free).

---

## 📋 **Current Status Check**

### Check Your Railway Setup

```bash
# Check if project is linked
railway status

# Check current services
railway service status

# Check environment variables
railway variables

# Check database setup
./check_railway_db.sh
```

---

## 🚀 **Step-by-Step Deployment Process**

### **Phase 1: Project Setup** ✅ COMPLETED

- [x] Railway account created
- [x] Project linked: `zesty-bravery`
- [x] Service deployed: `apm-observability`
- [x] Status: SUCCESS
- [x] `railway.json` configuration created
- [x] **All changes committed and pushed to GitHub** ✅
- [x] Railway has access to latest configuration files

### **Phase 2: Database Setup** ⏳ IN PROGRESS

#### **Option A: CLI Method (Recommended)**

```bash
railway add
# Interactive selection:
# → Database
# → PostgreSQL
# → Press SPACE to select
# → Press ENTER to confirm
# → Choose free tier when prompted
```

#### **Option B: Web Dashboard Method**

```bash
# Open Railway dashboard in browser
railway open

# In browser:
# → Click "New" button
# → Select "Database"
# → Choose "PostgreSQL"
# → Select free tier option
# → Click "Create"
```

#### **Verify Database Added**

```bash
# Check if database variables appear
railway variables

# Look for these variables (Railway auto-generates them):
# POSTGRES_HOST
# POSTGRES_PORT
# POSTGRES_DB
# POSTGRES_USER
# POSTGRES_PASSWORD
# DATABASE_URL
```

### **Phase 3: Environment Configuration**

#### **Run Environment Setup Script**

```bash
./setup_railway_env.sh
```

**What this script sets:**

- `DJANGO_DEBUG=0` (production mode)
- `DJANGO_SECRET_KEY` (randomly generated)
- `DJANGO_ALLOWED_HOSTS` (Railway domain)
- `DJANGO_TIME_ZONE=UTC`
- `DB_SSLMODE=require` (SSL for Railway Postgres)
- `DB_CONN_MAX_AGE=60` (connection pooling)
- `GUNICORN_WORKERS=2` (optimized for 512MB limit)
- `GUNICORN_TIMEOUT=30` (faster timeouts)
- `GUNICORN_BIND=0.0.0.0:${PORT:-8000}`
- `ENVIRONMENT=production`

### **Phase 4: TimescaleDB Setup**

#### **Connect to PostgreSQL**

```bash
railway connect postgres
```

#### **Enable TimescaleDB Extension**

```sql
-- Run this SQL command in the PostgreSQL shell:
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Verify it's enabled:
SELECT * FROM pg_extension WHERE extname = 'timescaledb';

-- Exit PostgreSQL shell:
\q
```

### **Phase 5: Redeploy Application**

#### **Trigger Redeployment**

```bash
railway up
```

#### **Monitor Deployment**

```bash
# Check deployment status
railway service status

# View build logs
railway logs

# View runtime logs
railway logs --service apm-observability
```

### **Phase 6: Testing & Verification**

#### **Open Your Live Application**

```bash
railway open
```

#### **Test Health Endpoints**

```bash
# Get your Railway URL from the output above, then test:
curl https://your-app-name.railway.app/api/health/
curl https://your-app-name.railway.app/api/health/?db=1
```

#### **Test API Endpoints**

```bash
# Test main API endpoints
curl https://your-app-name.railway.app/api/docs/
curl https://your-app-name.railway.app/api/ingest/  # POST endpoint
curl https://your-app-name.railway.app/api/kpis/
```

---

## 🔧 **Troubleshooting Guide**

### **Issue: Database Not Added**

**Symptoms:** No POSTGRES\_\* variables in `railway variables`
**Solutions:**

1. Try CLI method again: `railway add`
2. Use web dashboard: `railway open`
3. Check Railway service status: `railway service status`

### **Issue: Environment Variables Not Set**

**Symptoms:** App fails to start, database connection errors
**Solutions:**

1. Run setup script: `./setup_railway_env.sh`
2. Manually check variables: `railway variables`
3. Verify database variables exist first

### **Issue: TimescaleDB Not Enabled**

**Symptoms:** Hourly/daily endpoints return errors
**Solutions:**

1. Connect to database: `railway connect postgres`
2. Run: `CREATE EXTENSION IF NOT EXISTS timescaledb;`
3. Redeploy: `railway up`

### **Issue: App Won't Start**

**Symptoms:** Deployment fails or health check fails
**Solutions:**

1. Check logs: `railway logs`
2. Verify environment variables
3. Check database connectivity
4. Ensure TimescaleDB is enabled

### **Issue: SSL/HTTPS Not Working**

**Symptoms:** Mixed content warnings, insecure connection
**Solutions:**

- Railway provides automatic SSL - no configuration needed
- Check if you're using `https://` in URLs
- Verify domain is correct

---

## 📊 **Railway Free Tier Limits**

| Resource      | Limit        | Notes                        |
| ------------- | ------------ | ---------------------------- |
| RAM           | 512MB        | Enough for your Django API   |
| Storage       | 1GB          | PostgreSQL database storage  |
| Hours         | 100/month    | ~3 hours/day, resets monthly |
| Bandwidth     | Unlimited    | For your API usage           |
| SSL           | ✅ Automatic | Free HTTPS included          |
| Custom Domain | ✅ Free      | your-app.railway.app         |

---

## 🎯 **Expected Railway URLs**

After successful deployment, your app will be available at:

- **Main App:** `https://zesty-bravery.up.railway.app`
- **API Health:** `https://zesty-bravery.up.railway.app/api/health/`
- **API Docs:** `https://zesty-bravery.up.railway.app/api/docs/`
- **Database:** Internal PostgreSQL (not publicly accessible)

---

## 🚀 **Quick Commands Reference**

```bash
# Status checks
railway status                    # Project status
railway service status           # Service status
railway variables               # Environment variables
./check_railway_db.sh           # Database check

# Database management
railway add                     # Add services
railway connect postgres        # Connect to database

# Deployment
railway up                      # Deploy/redeploy
railway logs                    # View logs
railway open                    # Open in browser

# Environment
./setup_railway_env.sh          # Set environment variables
```

---

## ✅ **Success Checklist**

- [ ] Railway project linked (`zesty-bravery`)
- [ ] PostgreSQL database added
- [ ] Environment variables configured
- [ ] TimescaleDB extension enabled
- [ ] Application redeployed successfully
- [ ] Health endpoint returns `{"status": "ok"}`
- [ ] Database health check passes
- [ ] API endpoints accessible
- [ ] SSL certificate working (HTTPS)

---

## 🎉 **Congratulations!**

Once all steps are complete, your APM Observability platform will be live and free on Railway with:

- ✅ Automatic SSL/HTTPS
- ✅ PostgreSQL with TimescaleDB
- ✅ Docker container deployment
- ✅ 24/7 uptime (with sleep after inactivity)
- ✅ No credit card required

**Your API will be available at:** `https://zesty-bravery.up.railway.app/api/`

---

## 📞 **Need Help?**

If you encounter issues:

1. Check the troubleshooting section above
2. Run diagnostic commands
3. Check Railway logs: `railway logs`
4. Visit Railway documentation: `railway docs`

**Current Phase:** Database Setup - Run `railway add` and select PostgreSQL!</content>
<parameter name="filePath">/Users/nawfalrazouk/apm-observability/RAILWAY_DEPLOYMENT_COMPLETE.md
