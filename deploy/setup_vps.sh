#!/usr/bin/env bash
# =============================================================================
# SaKgaZé — Automated VPS Provisioning (Ubuntu 24.04 LTS / Debian 12)
# Usage: chmod +x setup_vps.sh && sudo ./setup_vps.sh
# =============================================================================
set -euo pipefail

# --- Colors ---
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[+]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
err()   { echo -e "${RED}[x]${NC} $*"; exit 1; }

# --- Must be root ---
if [[ $EUID -ne 0 ]]; then err "This script must be run as root (sudo ./setup_vps.sh)"; fi

# === PROMPT FOR CONFIGURATION ================================================
echo ""
echo "  ╔══════════════════════════════════════════════════════╗"
echo "  ║     SaKgaZé — Production VPS Provisioning           ║"
echo "  ╚══════════════════════════════════════════════════════╝"
echo ""

read -p "  Domain name (e.g. sakgaze.fr):       " DOMAIN
read -p "  SSL notification email:              " EMAIL
read -sp "  Database password for user 'sakgaze': " DB_PASS; echo ""
echo ""

if [[ -z "$DOMAIN" || -z "$EMAIL" || -z "$DB_PASS" ]]; then
    err "All fields are required."
fi

INSTALL_DIR="/opt/sakgaze"
REPO_URL="${REPO_URL:-https://github.com/your-org/sakgaze-caribbean.git}"

# === SYSTEM UPDATE & BASE PACKAGES ===========================================
info "Updating system packages..."
apt-get update -qq && apt-get upgrade -y -qq

info "Installing base dependencies..."
apt-get install -y -qq \
    curl wget git ca-certificates gnupg lsb-release \
    build-essential python3.14 python3.14-venv python3.14-dev \
    libpq-dev libgdal-dev nginx certbot python3-certbot-nginx \
    ufw software-properties-common

# === POSTGRESQL 17 + POSTGIS 3 ==============================================
info "Installing PostgreSQL 17 + PostGIS 3..."
if ! dpkg -l | grep -q postgresql-17; then
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/postgresql.gpg
    echo "deb [signed-by=/usr/share/keyrings/postgresql.gpg] http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list
    apt-get update -qq
    apt-get install -y -qq postgresql-17 postgresql-17-postgis-3 postgresql-17-postgis-3-scripts
fi

# Start PostgreSQL on port 5433 (avoid conflicts)
pg_lsclusters | grep -q 17 || pg_createcluster 17 main --port=5433
pg_ctlcluster 17 main start 2>/dev/null || true
systemctl enable postgresql@17-main

# === DATABASE SETUP ==========================================================
info "Creating database and user..."
su - postgres -c "psql -p 5433 -c \"CREATE USER sakgaze WITH PASSWORD '${DB_PASS}';\"" 2>/dev/null || warn "User already exists"
su - postgres -c "psql -p 5433 -c \"CREATE DATABASE sakgaze OWNER sakgaze;\"" 2>/dev/null || warn "Database already exists"
su - postgres -c "psql -p 5433 -d sakgaze -c \"CREATE EXTENSION IF NOT EXISTS postgis;\"" 2>/dev/null

# === APPLICATION USER & DIRECTORIES =========================================
info "Creating application user and directories..."
id -u sakgaze >/dev/null 2>&1 || useradd -m -s /bin/bash sakgaze
mkdir -p "$INSTALL_DIR" /var/log/sakgaze /var/www/certbot
chown -R sakgaze:sakgaze "$INSTALL_DIR" /var/log/sakgaze

# === CLONE REPOSITORY =======================================================
info "Cloning repository..."
if [[ -d "$INSTALL_DIR/.git" ]]; then
    warn "Repository already exists, pulling latest..."
    su - sakgaze -c "cd $INSTALL_DIR && git pull"
else
    su - sakgaze -c "git clone $REPO_URL $INSTALL_DIR"
fi

# === PYTHON VIRTUAL ENVIRONMENT =============================================
info "Setting up Python virtual environment..."
su - sakgaze -c "cd $INSTALL_DIR && python3.14 -m venv .venv"
su - sakgaze -c "cd $INSTALL_DIR && .venv/bin/pip install --upgrade pip -q"
su - sakgaze -c "cd $INSTALL_DIR && .venv/bin/pip install --no-input \
    fastapi uvicorn[standard] pydantic sqlalchemy geoalchemy2 psycopg2-binary \
    shapely geopandas rasterio numpy scikit-learn pillow httpx requests \
    python-dotenv pytz apscheduler pytest pytest-asyncio"

# === INITIALIZE DATABASE SCHEMA =============================================
info "Initializing database tables and spatial indexes..."
su - sakgaze -c "cd $INSTALL_DIR && PYTHONPATH=. .venv/bin/python -c 'from backend.src.database import init_db; init_db(); print(\"DB OK\")'"

# === NGINX CONFIGURATION ====================================================
info "Configuring Nginx..."
# Copy template and substitute domain
sed "s/<DOMAIN>/${DOMAIN}/g" "$INSTALL_DIR/deploy/nginx.conf" > /etc/nginx/sites-available/sakgaze
ln -sf /etc/nginx/sites-available/sakgaze /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# === SYSTEMD SERVICES =======================================================
info "Installing systemd services..."
# Backend service
sed "s|<DB_PASSWORD>|${DB_PASS}|g" "$INSTALL_DIR/deploy/sakgaze-backend.service" \
    > /etc/systemd/system/sakgaze-backend.service
# Scheduler service + timer
cp "$INSTALL_DIR/deploy/sakgaze-scheduler.service" /etc/systemd/system/
cp "$INSTALL_DIR/deploy/sakgaze-scheduler.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable sakgaze-backend
systemctl enable sakgaze-scheduler.timer
systemctl start sakgaze-backend
systemctl start sakgaze-scheduler.timer

# === FIREWALL (UFW) =========================================================
info "Configuring UFW firewall..."
ufw --force reset >/dev/null
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp   # SSH
ufw allow 80/tcp   # HTTP
ufw allow 443/tcp  # HTTPS
ufw --force enable

# === SSL CERTIFICATE (Let's Encrypt) ========================================
info "Obtaining SSL certificate via Let's Encrypt..."
certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" \
    --non-interactive --agree-tos -m "$EMAIL" \
    --redirect 2>/dev/null || warn "Certbot failed — run manually: certbot --nginx -d $DOMAIN"

# === DONE ====================================================================
echo ""
echo "  ╔══════════════════════════════════════════════════════╗"
echo "  ║     SaKgaZé deployment complete!                     ║"
echo "  ╠══════════════════════════════════════════════════════╣"
echo "  ║  Backend:   https://${DOMAIN}/health                 ║"
echo "  ║  Dashboard: https://${DOMAIN}/                       ║"
echo "  ║  Status:    systemctl status sakgaze-backend         ║"
echo "  ║  Logs:      journalctl -u sakgaze-backend -f         ║"
echo "  ╚══════════════════════════════════════════════════════╝"
echo ""
info "Setup script completed. Reboot recommended for all changes to take effect."
