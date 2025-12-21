#!/bin/bash
# Certbot SSL Certificate Management Script
# This script handles SSL certificate generation and renewal for production

set -euo pipefail

# Configuration
DOMAIN="${DOMAIN:-localhost}"
EMAIL="${SSL_EMAIL:-admin@example.com}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERT_DIR="${SCRIPT_DIR}"
WEBROOT="/var/www/certbot"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}" >&2
}

warn() {
    echo -e "${YELLOW}[WARN] $1${NC}"
}

# Create webroot directory for HTTP-01 challenge
setup_webroot() {
    log "Setting up webroot directory for ACME challenges..."
    mkdir -p "$WEBROOT"
    chmod 755 "$WEBROOT"
}

# Generate self-signed certificate for development
generate_self_signed() {
    log "Generating self-signed certificate for development..."
    mkdir -p "$CERT_DIR"

    # Check if we're running in container or host
    if [ -w "$CERT_DIR" ]; then
        # Running on host or with write permissions
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout "$CERT_DIR/private.key" \
            -out "$CERT_DIR/public.crt" \
            -subj "/C=US/ST=State/L=City/O=Organization/CN=$DOMAIN"

        chmod 600 "$CERT_DIR/private.key"
        chmod 644 "$CERT_DIR/public.crt"

        log "Self-signed certificate generated successfully"
    else
        # Running in container without write permissions
        log "Certificate directory not writable. Please run this script on the host or ensure proper permissions."
        log "Certificates should be generated in: $CERT_DIR"
        exit 1
    fi
}

# Obtain Let's Encrypt certificate
obtain_letsencrypt_cert() {
    log "Obtaining Let's Encrypt certificate for $DOMAIN..."

    if [ "$DOMAIN" = "localhost" ]; then
        warn "Domain is localhost - using self-signed certificate instead"
        generate_self_signed
        return
    fi

    # Check if certbot is available
    if ! command -v certbot &> /dev/null; then
        error "certbot is not installed. Please install certbot first."
        error "For Ubuntu/Debian: apt-get install certbot"
        error "For CentOS/RHEL: yum install certbot"
        exit 1
    fi

    # Obtain certificate
    certbot certonly --webroot \
        --webroot-path "$WEBROOT" \
        --email "$EMAIL" \
        --agree-tos \
        --no-eff-email \
        --domain "$DOMAIN"

    # Create symlinks for nginx
    ln -sf "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" "$CERT_DIR/public.crt"
    ln -sf "/etc/letsencrypt/live/$DOMAIN/privkey.pem" "$CERT_DIR/private.key"

    log "Let's Encrypt certificate obtained successfully"
}

# Renew certificates
renew_certificates() {
    log "Checking for certificate renewal..."

    if [ "$DOMAIN" = "localhost" ]; then
        log "Development mode - no renewal needed for self-signed certificate"
        return
    fi

    certbot renew --quiet

    # Reload nginx if certificates were renewed
    if [ -f /var/run/nginx.pid ]; then
        log "Reloading nginx configuration..."
        nginx -s reload
    fi

    log "Certificate renewal check completed"
}

# Setup cron job for automatic renewal
setup_cron_renewal() {
    log "Setting up automatic certificate renewal..."

    if [ "$DOMAIN" = "localhost" ]; then
        log "Development mode - skipping cron setup"
        return
    fi

    # Add cron job for renewal (runs twice daily)
    CRON_JOB="0 */12 * * * /usr/bin/certbot renew --quiet --post-hook 'nginx -s reload'"

    # Check if cron job already exists
    if ! crontab -l 2>/dev/null | grep -q "certbot renew"; then
        (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
        log "Certificate renewal cron job added"
    else
        log "Certificate renewal cron job already exists"
    fi
}

# Main function
main() {
    local action="${1:-setup}"

    case "$action" in
        "setup")
            setup_webroot
            if [ "$DOMAIN" = "localhost" ]; then
                generate_self_signed
            else
                obtain_letsencrypt_cert
            fi
            setup_cron_renewal
            ;;
        "renew")
            renew_certificates
            ;;
        "self-signed")
            generate_self_signed
            ;;
        *)
            error "Usage: $0 {setup|renew|self-signed}"
            exit 1
            ;;
    esac
}

main "$@"