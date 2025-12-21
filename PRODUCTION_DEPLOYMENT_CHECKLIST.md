# Production Deployment Checklist

This document outlines the steps for deploying the APM Observability platform to production with SSL/HTTPS enabled.

## 🚀 Quick Free Deployment Options

### Option 1: Railway (RECOMMENDED - No Credit Card)

- ✅ **Completely FREE** - No credit card required
- ✅ Docker support with automatic SSL
- ✅ PostgreSQL with TimescaleDB extension
- ✅ 512MB RAM, 100 hours/month
- **Setup time:** 10 minutes
- **Complete Guide:** See `RAILWAY_DEPLOYMENT_COMPLETE.md`
- **Current Status:** Project linked, database setup in progress
- **See:** `FREE_DEPLOYMENT_GUIDE.md` and `railway-deployment.md`

### Option 2: Oracle Cloud Free Tier

- ✅ **FREE forever** - 2 VMs, 200GB storage
- ✅ Most powerful free option
- ✅ Requires credit card verification (no charges)
- **Setup time:** 30 minutes

### Option 3: Render Free Tier

- ✅ **FREE** - No credit card required
- ✅ 750 hours/month, automatic SSL
- ✅ Good Docker support
- **Setup time:** 15 minutes

## 1. Pre-Deployment Preparation

### Environment Setup

- [ ] Choose production environment:
  - [ ] **Railway** (free, easiest)
  - [ ] **Oracle Cloud** (free, most powerful)
  - [ ] **Render** (free, good balance)
  - [ ] VPS/Cloud provider (paid options)
- [ ] Set up domain name and DNS configuration (optional for free tiers)
- [ ] Configure firewall (open ports 80, 443, 5432 for DB if needed)
- [ ] Install Docker and Docker Compose on production server (if using VPS)
- [ ] Set up SSH access and security (if using VPS)

### Domain & SSL Configuration

- [ ] Purchase/register domain name
- [ ] Configure DNS A/AAAA records pointing to server IP
- [ ] Verify domain propagation (`nslookup yourdomain.com`)
- [ ] Set environment variables:
  ```bash
  export DOMAIN=yourdomain.com
  export SSL_EMAIL=admin@yourdomain.com
  export ENVIRONMENT=production
  ```

### Security Hardening

- [ ] Update system packages (`apt update && apt upgrade`)
- [ ] Configure firewall (ufw/firewalld)
- [ ] Set up fail2ban for SSH protection
- [ ] Configure log rotation
- [ ] Set up monitoring (optional)

## 2. Application Deployment

### Code Deployment

- [ ] Clone repository on production server
- [ ] Create production `.env` file with secure passwords
- [ ] Test Docker services locally (optional)
- [ ] Run production deployment script:
  ```bash
  ./deploy-production.sh deploy
  ```

### SSL Certificate Setup

- [ ] Verify Let's Encrypt certificate generation
- [ ] Test HTTPS access: `curl -I https://yourdomain.com/api/health/`
- [ ] Verify HTTP to HTTPS redirect
- [ ] Check SSL certificate validity (SSL Labs test)

### Service Verification

- [ ] Verify all services are running: `docker compose ps`
- [ ] Check application logs: `docker compose logs web`
- [ ] Test API endpoints over HTTPS
- [ ] Verify database connectivity
- [ ] Test MinIO access over HTTPS

## 3. Production Configuration

### Database Setup

- [ ] Verify TimescaleDB/PostgreSQL is running
- [ ] Run initial migrations: `docker compose exec web python manage.py migrate`
- [ ] Create superuser: `docker compose exec web python manage.py createsuperuser`
- [ ] Load initial data if needed

### Nginx Configuration

- [ ] Verify SSL configuration and security headers
- [ ] Test rate limiting (if configured)
- [ ] Verify HSTS headers are enabled
- [ ] Check OCSP stapling (for production certificates)

### Backup Configuration

- [ ] Set up automated backup schedule
- [ ] Configure backup storage (separate from application server)
- [ ] Test backup script with SSL: `./docker/backup/backup.sh`
- [ ] Set up backup monitoring and alerts

## 4. Monitoring & Maintenance

### Application Monitoring

- [ ] Set up health check endpoints monitoring
- [ ] Configure log aggregation (ELK stack, etc.)
- [ ] Set up error tracking (Sentry, etc.)
- [ ] Configure performance monitoring

### System Monitoring

- [ ] Monitor disk space, CPU, memory usage
- [ ] Set up alerts for service failures
- [ ] Configure log rotation for Docker logs
- [ ] Set up automated updates (carefully!)

### SSL Certificate Monitoring

- [ ] Monitor certificate expiration (certbot handles renewal)
- [ ] Set up alerts for certificate issues
- [ ] Test certificate renewal process

## 5. Security & Compliance

### Security Audit

- [ ] Run security scan (nmap, nikto, etc.)
- [ ] Verify SSL configuration (sslscan, testssl.sh)
- [ ] Check for exposed sensitive information
- [ ] Review firewall rules and network security

### Access Control

- [ ] Configure proper user permissions
- [ ] Set up SSH key authentication only
- [ ] Disable root login
- [ ] Configure sudo access appropriately

### Data Protection

- [ ] Verify data encryption at rest
- [ ] Check backup encryption
- [ ] Set up proper database user permissions
- [ ] Configure data retention policies

## 6. Performance Optimization

### Application Performance

- [ ] Configure Gunicorn workers based on server resources
- [ ] Set up connection pooling for database
- [ ] Configure caching (Redis, etc.) if needed
- [ ] Optimize static file serving

### Database Optimization

- [ ] Configure PostgreSQL for production workload
- [ ] Set up TimescaleDB chunk policies
- [ ] Configure connection limits
- [ ] Set up database monitoring

### Infrastructure Optimization

- [ ] Configure Docker resource limits
- [ ] Set up container health checks
- [ ] Configure restart policies
- [ ] Optimize Docker image sizes

## 7. Documentation & Handover

### Production Documentation

- [ ] Document production environment setup
- [ ] Create runbooks for common operations
- [ ] Document backup/restore procedures
- [ ] Create incident response procedures

### Team Handover

- [ ] Document access credentials and procedures
- [ ] Set up knowledge base/wiki
- [ ] Train operations team
- [ ] Establish support channels

## 8. Go-Live Checklist

### Final Verification

- [ ] All services running and healthy
- [ ] SSL certificates valid and auto-renewing
- [ ] Backups working and tested
- [ ] Monitoring and alerting configured
- [ ] Documentation complete and accessible
- [ ] Support team trained and ready

### Go-Live Steps

- [ ] Update DNS to point to production (if using blue-green)
- [ ] Monitor application for first 24-48 hours
- [ ] Verify all endpoints working
- [ ] Confirm backup successful post-launch
- [ ] Announce successful deployment

---

## Priority Order

1. **Pre-deployment preparation** (infrastructure, security)
2. **SSL certificate setup** (critical for HTTPS)
3. **Application deployment** (core functionality)
4. **Monitoring & maintenance** (operational readiness)
5. **Security & compliance** (production requirements)
6. **Performance optimization** (scaling readiness)
7. **Documentation & handover** (team enablement)

## Rollback Plan

- Keep previous version ready for quick rollback
- Document rollback procedures
- Test rollback process before go-live
- Have backup of production data before deployment

## Emergency Contacts

- [ ] Development team contacts
- [ ] Infrastructure/DevOps contacts
- [ ] Business stakeholders
- [ ] External service providers (domain, hosting)

---

**Note:** This checklist assumes SSL/HTTPS implementation is complete as per SSL_POST_IMPLEMENTATION_UPDATES.md</content>
<parameter name="filePath">/Users/nawfalrazouk/apm-observability/PRODUCTION_DEPLOYMENT_CHECKLIST.md
