# Railway Production Deployment Issue - SSL Redirect & Healthcheck Failure

## Problem Summary

The Django APM Observability platform fails to deploy to Railway free tier due to healthcheck failures. The Railway healthcheck at `/api/health/` returns "service unavailable" despite the application building successfully.

## Root Cause Analysis

### Issue Description
- Railway performs healthchecks on deployed applications to ensure they're running properly
- The healthcheck endpoint is configured as `/api/health/` in `railway.json`
- Railway accesses this endpoint over HTTP internally, but Django's SSL redirect middleware redirects HTTP requests to HTTPS
- This creates an infinite redirect loop: Railway → HTTP → Django redirects to HTTPS → Railway receives redirect instead of 200 OK

### Technical Details

**SSL Configuration in `apm_platform/settings.py`:**
```python
SECURE_SSL_REDIRECT = False if RUNNING_TESTS else True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_REDIRECT_EXEMPT = [r'^/api/health/$']  # Initially tried this approach
```

**Railway Configuration in `railway.json`:**
```json
{
  "deploy": {
    "healthcheckPath": "/api/health/",
    "healthcheckTimeout": 300
  }
}
```

**Health Endpoint in `observability/views.py`:**
```python
class HealthView(APIView):
    def get(self, request, *args, **kwargs):
        return Response({"status": "ok"}, status=status.HTTP_200_OK)
```

## Solutions Attempted

### 1. SECURE_REDIRECT_EXEMPT Setting (Failed)
- Added `SECURE_REDIRECT_EXEMPT = [r'^api/health/$']` to settings
- Initially used incorrect regex pattern without leading slash
- Corrected to `SECURE_REDIRECT_EXEMPT = [r'^/api/health/$']`
- **Result:** Still failed - middleware processes redirect before view logic

### 2. HealthView Dispatch Method Override (Current Solution)
- Added `dispatch()` method to `HealthView` that temporarily disables SSL redirect
- Directly bypasses `SECURE_SSL_REDIRECT` for healthcheck requests
- **Status:** Implemented and deployed, awaiting test results

```python
def dispatch(self, request, *args, **kwargs):
    if request.path == '/api/health/':
        old_ssl_redirect = getattr(settings, 'SECURE_SSL_REDIRECT', False)
        settings.SECURE_SSL_REDIRECT = False
        try:
            return super().dispatch(request, *args, **kwargs)
        finally:
            settings.SECURE_SSL_REDIRECT = old_ssl_redirect
    return super().dispatch(request, *args, **kwargs)
```

## Deployment Status

### Build Status: ✅ SUCCESS
- Docker build completes successfully (13-14 seconds)
- All dependencies install correctly
- Static files collect properly
- Database migrations run successfully

### Healthcheck Status: ❌ FAILING
- Railway reports "service unavailable" for `/api/health/`
- Multiple retry attempts fail over 5-minute window
- Deployment rolls back due to healthcheck failure

### Environment Details
- **Platform:** Railway free tier
- **Database:** PostgreSQL (Railway managed)
- **SSL:** Automatic HTTPS with Let's Encrypt
- **Container:** Docker with Gunicorn
- **Framework:** Django 5.2.9 + Django REST Framework

## Why This Happens

1. **Railway Architecture:** Railway performs internal healthchecks over HTTP to avoid SSL certificate issues
2. **Django Security:** `SecurityMiddleware` enforces HTTPS redirects for all requests by default
3. **Middleware Order:** SSL redirect happens at middleware level, before view code executes
4. **Infinite Loop:** HTTP healthcheck → HTTPS redirect → Railway doesn't follow redirects for healthchecks

## Lessons Learned

1. **Middleware Processing Order:** SSL redirects happen before view dispatch, making `SECURE_REDIRECT_EXEMPT` ineffective for programmatic control
2. **Healthcheck Design:** Health endpoints should be designed to work with deployment platform requirements
3. **SSL Configuration:** Need careful handling of SSL redirects in containerized deployments
4. **Testing Strategy:** Local testing doesn't catch production SSL redirect issues

## Next Steps

1. **Monitor Current Deployment:** Check if the `dispatch()` method fix resolves the issue
2. **Alternative Solutions if Needed:**
   - Disable SSL redirect entirely for Railway (not ideal for security)
   - Use Railway-specific environment variables to conditionally disable SSL
   - Implement healthcheck at different URL pattern
3. **Long-term:** Consider Railway-specific deployment configuration

## Files Modified

- `apm_platform/settings.py`: Added SSL redirect exemption (attempted)
- `observability/views.py`: Added dispatch method to bypass SSL redirect
- `railway.json`: Healthcheck configuration (unchanged)

## Testing Commands

```bash
# Local healthcheck test
curl -s http://localhost:8002/api/health/

# Railway deployment
railway up

# Check Railway logs
railway logs
```

## Related Documentation

- Railway Healthcheck Documentation
- Django SSL/HTTPS Deployment Guide
- SecurityMiddleware Source Code
- Previous analysis: `TIMESCALEDB_MIGRATION_ANALYSIS.md`

---

**Status:** Awaiting Railway deployment results for current fix
**Date:** December 21, 2025
**Priority:** High - Blocks production deployment