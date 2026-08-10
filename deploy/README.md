# SaKgaZé — Production Deployment Guide

SaKgaZé is a Caribbean sargassum detection and drift forecasting platform combining
Sentinel-2 satellite imagery with physical drift modeling (wind + ocean currents).

## Architecture

```
┌──────────┐     ┌──────────────┐     ┌──────────────────┐
│  Nginx   │────▶│   FastAPI    │────▶│  PostgreSQL 17   │
│  :443    │     │   :8000      │     │  + PostGIS 3     │
│  reverse │     │   (uvicorn)  │     │  :5433           │
│  proxy   │     └──────┬───────┘     └──────────────────┘
│          │            │
│  static  │     ┌──────▼───────┐
│  files   │     │  Scheduler   │
│  :443    │     │  (systemd    │
└──────────┘     │   timer)     │
                 │  every 6h    │
                 └──────────────┘
```

## Prerequisites

- **VPS** with ≥ 4 GB RAM (Scaleway, Hetzner, DigitalOcean)
- **OS:** Ubuntu 24.04 LTS or Debian 12 (clean install)
- **Domain name** with DNS A-records pointing to VPS IP
- **SSH root access** to the VPS

## Quick Start

### 1. Purchase & Configure VPS

| Provider | Recommended Plan | RAM | Price |
|----------|-----------------|-----|-------|
| Scaleway | PLAY2-M | 4 GB | ~€16/mo |
| Hetzner  | CX32     | 4 GB | ~€13/mo |
| DigitalOcean | Basic Droplet | 4 GB | ~$24/mo |

### 2. Configure DNS

Add these A-records at your domain registrar:

```
Type  Name  Value           TTL
A     @     <VPS_IP>        3600
A     www   <VPS_IP>        3600
```

Wait for DNS propagation (5–30 minutes). Verify with:
```bash
dig +short sakgaze.fr
```

### 3. Clone & Deploy

SSH into your VPS and run:

```bash
git clone https://github.com/your-org/sakgaze-caribbean.git /opt/sakgaze
cd /opt/sakgaze
chmod +x deploy/setup_vps.sh
sudo ./deploy/setup_vps.sh
```

The script will prompt for:
- **Domain name** (e.g. `sakgaze.fr`)
- **SSL notification email**
- **Database password**

It then automatically:
1. Installs all system dependencies (PostgreSQL 17, PostGIS 3, Nginx, Python 3.14)
2. Creates the `sakgaze` database with PostGIS extensions
3. Sets up Python virtual environment and installs packages
4. Configures Nginx reverse proxy with SSL (Let's Encrypt)
5. Creates and starts systemd services
6. Configures UFW firewall (ports 22, 80, 443 only)

### 4. Verify Deployment

```bash
# Check backend health
curl https://sakgaze.fr/health
# → {"status":"ok"}

# Check API data endpoints
curl https://sakgaze.fr/api/v1/sakgaze/detections/latest | head -c 200
# → {"type":"FeatureCollection","features":[...]}

# Check systemd services
systemctl status sakgaze-backend
systemctl status sakgaze-scheduler.timer

# View logs
journalctl -u sakgaze-backend -f
tail -f /var/log/sakgaze/backend.log
tail -f /var/log/sakgaze/scheduler.log
```

### 5. Manual Pipeline Trigger

```bash
sudo -u sakgaze bash -c 'cd /opt/sakgaze && PYTHONPATH=. .venv/bin/python -m sakgaze.src.pipeline'
sudo -u sakgaze bash -c 'cd /opt/sakgaze && PYTHONPATH=. .venv/bin/python -m weathernext.src.pipeline'
sudo -u sakgaze bash -c 'cd /opt/sakgaze && PYTHONPATH=. .venv/bin/python -m drift.src.engine'
```

## File Structure

```
deploy/
├── nginx.conf                  Nginx reverse proxy configuration
├── sakgaze-backend.service     systemd unit for FastAPI backend
├── sakgaze-scheduler.service   systemd unit for pipeline execution
├── sakgaze-scheduler.timer     systemd timer (every 6 hours)
├── setup_vps.sh                Automated provisioning script
└── README.md                   This guide
```

## Monitoring

| Component | Command |
|---|---|
| Backend health | `curl https://sakgaze.fr/health` |
| Backend status | `systemctl status sakgaze-backend` |
| Backend logs | `journalctl -u sakgaze-backend -f` |
| Scheduler status | `systemctl status sakgaze-scheduler.timer` |
| Scheduler next run | `systemctl list-timers sakgaze-scheduler.timer` |
| Nginx access logs | `tail -f /var/log/nginx/sakgaze-access.log` |
| Nginx error logs | `tail -f /var/log/nginx/sakgaze-error.log` |
| PostgreSQL | `su - postgres -c "psql -p 5433 -d sakgaze"` |

## Security Notes

- UFW blocks all incoming ports except 22 (SSH), 80 (HTTP), 443 (HTTPS)
- FastAPI listens only on `127.0.0.1:8000` (not exposed to internet)
- PostgreSQL listens on `127.0.0.1:5433` (not exposed)
- SSL certificates auto-renew via Certbot cron job
- Systemd services run as unprivileged `sakgaze` user with `ProtectSystem=strict`

## Troubleshooting

**Nginx returns 502 Bad Gateway:**
```bash
systemctl restart sakgaze-backend
journalctl -u sakgaze-backend -n 50
```

**Database connection refused:**
```bash
systemctl start postgresql@17-main
pg_isready -p 5433
```

**SSL certificate expired:**
```bash
certbot renew --dry-run
certbot renew --force-renewal
```

**Pipeline fails (out of memory):**
Reduce workers in `sakgaze-backend.service` from 4 to 2, or upgrade to 8 GB VPS.
