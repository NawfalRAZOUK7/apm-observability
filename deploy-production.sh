#!/bin/bash
# Production SSL Certificate Setup and Deployment Script
# This script handles production SSL certificate setup and deployment

set -euo pipefail

# Configuration - Override with environment variables
DOMAIN="${DOMAIN:-yourdomain.com}"
EMAIL="${SSL_EMAIL:-admin@yourdomain.com}"
ENVIRONMENT="${ENVIRONMENT:-production}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

info() {
    echo -e "${BLUE}[INFO] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[WARN] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}" >&2
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."

    # Check if Docker is running
    if ! docker info >/dev/null 2>&1; then
        error "Docker is not running. Please start Docker first."
        exit 1
    fi

    # Check if Docker Compose is available
    if ! command -v docker-compose >/dev/null 2>&1 && ! docker compose version >/dev/null 2>&1; then
        error "Docker Compose is not available."
        exit 1
    fi

    # Check domain configuration
    if [ "$DOMAIN" = "yourdomain.com" ]; then
        error "Please set DOMAIN environment variable to your actual domain"
        error "Example: export DOMAIN=apm.yourcompany.com"
        exit 1
    fi

    # Validate domain format
    if [ "$DOMAIN" != "localhost" ] && ! echo "$DOMAIN" | grep -qE '^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'; then
        error "Invalid domain format: $DOMAIN"
        exit 1
    fi

    log "Prerequisites check passed"
}

# Setup SSL certificates
setup_ssl() {
    log "Setting up SSL certificates for $DOMAIN..."

    # Export environment variables for the SSL setup script
    export DOMAIN EMAIL

    # Run SSL setup
    if [ "$ENVIRONMENT" = "production" ]; then
        info "Setting up production SSL certificates with Let's Encrypt..."
        ./docker/certs/setup-ssl.sh setup
    else
        info "Setting up development SSL certificates..."
        ./docker/certs/setup-ssl.sh self-signed
    fi
}

# Deploy application
deploy_application() {
    log "Deploying application..."

    # Create .env file if it doesn't exist
    if [ ! -f .env ]; then
        warn ".env file not found. Creating from template..."
        cp .env.example .env 2>/dev/null || create_env_file
    fi

    # Start services
    if [ "$ENVIRONMENT" = "production" ]; then
        info "Starting production services (with certbot)..."
        docker-compose --profile production up -d
    else
        info "Starting development services..."
        docker-compose up -d
    fi

    # Wait for services to be healthy
    log "Waiting for services to start..."
    sleep 30

    # Check service health
    check_services
}

# Check service health
check_services() {
    log "Checking service health..."

    # Check nginx
    if docker-compose ps nginx | grep -q "Up"; then
        log "✓ Nginx is running"
    else
        error "✗ Nginx failed to start"
        docker-compose logs nginx
        exit 1
    fi

    # Check web application
    if docker-compose ps web | grep -q "Up"; then
        log "✓ Web application is running"
    else
        error "✗ Web application failed to start"
        docker-compose logs web
        exit 1
    fi

    # Check database
    if docker-compose ps db | grep -q "Up"; then
        log "✓ Database is running"
    else
        error "✗ Database failed to start"
        docker-compose logs db
        exit 1
    fi
}

# Test SSL configuration
test_ssl() {
    log "Testing SSL configuration..."

    # Wait a bit for SSL to be ready
    sleep 5

    # Test HTTPS connection
    if curl -k -s -o /dev/null -w "%{http_code}" "https://localhost:8443/api/requests/" | grep -q "200\|401\|403"; then
        log "✓ HTTPS connection successful"
    else
        warn "⚠ HTTPS connection test failed - this may be normal if authentication is required"
    fi

    # Test HTTP to HTTPS redirect
    if curl -s -o /dev/null -w "%{http_code}" "http://localhost/" | grep -q "301"; then
        log "✓ HTTP to HTTPS redirect working"
    else
        warn "⚠ HTTP redirect test failed"
    fi

    # Test SSL certificate
    if echo | openssl s_client -connect localhost:8443 -servername "$DOMAIN" 2>/dev/null | openssl x509 -noout -dates >/dev/null 2>&1; then
        log "✓ SSL certificate is valid"
    else
        error "✗ SSL certificate validation failed"
    fi
}

# Create basic .env file
create_env_file() {
    cat > .env << EOF
# Database Configuration
POSTGRES_DB=apm
POSTGRES_USER=apm
POSTGRES_PASSWORD=secure_password_here
POSTGRES_APP_USER=apm_app
POSTGRES_APP_PASSWORD=secure_app_password_here
POSTGRES_READONLY_USER=apm_readonly
POSTGRES_READONLY_PASSWORD=secure_readonly_password_here
POSTGRES_HOST=db
POSTGRES_PORT=5432

# Django Configuration
SECRET_KEY=your-secret-key-here
DEBUG=False
DJANGO_ALLOWED_HOSTS=localhost,$DOMAIN
FORCE_SQLITE=False

# SSL Configuration
SSL_VERIFY=true

# Domain Configuration
DOMAIN=$DOMAIN
SSL_EMAIL=$EMAIL
EOF

    warn "Created basic .env file. Please update passwords and secret key!"
}

# Show production deployment instructions
show_production_instructions() {
    echo
    log "🎉 Production deployment completed!"
    echo
    info "Next steps for production deployment:"
    echo
    echo "1. DNS Configuration:"
    echo "   - Point your domain $DOMAIN to this server's IP address"
    echo "   - Ensure ports 80 and 443 are open in your firewall"
    echo
    echo "2. SSL Certificate Renewal:"
    echo "   - Certificates auto-renew every 60 days"
    echo "   - Monitor certbot logs: docker-compose logs certbot"
    echo
    echo "3. Monitoring:"
    echo "   - Check service health: docker-compose ps"
    echo "   - View logs: docker-compose logs [service]"
    echo "   - Monitor SSL: https://www.ssllabs.com/ssltest/analyze.html?d=$DOMAIN"
    echo
    echo "4. Backup Configuration:"
    echo "   - Test backup/restore: docker-compose -f docker/docker-compose.backup.yml up -d"
    echo "   - Configure automated backups as needed"
    echo
    echo "5. Security Hardening:"
    echo "   - Change default database passwords in .env"
    echo "   - Set up firewall rules"
    echo "   - Configure log rotation"
    echo "   - Set up monitoring and alerting"
    echo
}

# Main function
main() {
    local action="${1:-deploy}"

    echo "=========================================="
    echo "APM Observability - Production Deployment"
    echo "=========================================="
    echo "Domain: $DOMAIN"
    echo "Email: $EMAIL"
    echo "Environment: $ENVIRONMENT"
    echo "=========================================="
    echo

    case "$action" in
        "deploy")
            check_prerequisites
            setup_ssl
            deploy_application
            test_ssl
            show_production_instructions
            ;;
        "ssl-setup")
            check_prerequisites
            setup_ssl
            ;;
        "test")
            test_ssl
            ;;
        *)
            error "Usage: $0 {deploy|ssl-setup|test}"
            error "  deploy    - Full production deployment"
            error "  ssl-setup - Setup SSL certificates only"
            error "  test      - Test SSL configuration"
            exit 1
            ;;
    esac
}

main "$@"