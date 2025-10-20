# Lalten.org Configuration Summary

**Last Updated**: 2025-10-09

> **Note**: This document is automatically updated whenever configuration changes are made to the website infrastructure.

---

## Overview

Personal/family website hosting static pages and two FastHTML web applications for menu planning and shopping list management. Future webapps will be Streamlit or FastHTML applications hosted from folders in `/root/lalten/`.

---

## Nginx Configuration

### Primary Site: lalten.org

**Config File**: `/etc/nginx/sites-available/lalten.org`
**Enabled**: Yes (symlinked in `/etc/nginx/sites-enabled/`)

#### Server Details
- **Domains**: `lalten.org`, `www.lalten.org`
- **SSL/TLS**: Let's Encrypt certificates managed by Certbot
  - Certificate: `/etc/letsencrypt/live/lalten.org/fullchain.pem`
  - Private Key: `/etc/letsencrypt/live/lalten.org/privkey.pem`
- **HTTP→HTTPS**: Automatic redirect from port 80 to 443

#### Routes

| Path | Destination | Type | Details |
|------|-------------|------|---------|
| `/` | `/var/www/html/` | Static files | Default: `index.html` |
| `/notes`, `/notes/` | `http://127.0.0.1:8765` | Reverse proxy | Shopping list webapp |
| `/menu`, `/menu/` | `http://127.0.0.1:8742` | Reverse proxy | Menu planning webapp |
| `/pages/` | `/root/lalten/pages/` | Static files | Directory listing enabled |

**Proxy Headers Set**:
- `Host: $host`
- `X-Real-IP: $remote_addr`

---

## Static Content

### Landing Page
**File**: `/var/www/html/index.html` → symlink to `/root/lalten/index.html`

**Design**:
- Black background with green monospace text (terminal style)
- Links to three personal websites:
  - Apoorva: https://apoorvalal.github.io
  - Chunyi: https://jesscyzhao.github.io/

### Pages Directory
**Location**: `/root/lalten/pages/`
**Access**: https://lalten.org/pages/

**Contents**:
- `counting_did.html` (6.1 MB)
- `test.html` (1.7 KB)

**Features**: Directory autoindex enabled (shows file listing with sizes and dates)

---

## Web Applications

Both applications use **FastHTML** framework with SQLite databases.

### 1. Menu App (Family Menu Planner)

**Location**: `/root/lalten/menu/`
**Main File**: `main.py`
**Port**: `8742` (localhost)
**URL**: https://lalten.org/menu

#### Features
- Add menu items (meal plans)
- Edit existing items
- Delete items
- Chronological display (newest first)

#### Database
**File**: `menu.db`
**Table**: `menu_items`
- `id` (int, primary key)
- `content` (text)
- `created_at` (timestamp)

#### Dependencies
**File**: `requirements.txt`
- FastHTML framework

#### Environment
- Python virtual environment: `.venv/`
- Session key: `.sesskey`

---

### 2. Notes App (Family Shopping List)

**Location**: `/root/lalten/notes/`
**Main File**: `main.py`
**Port**: `8765` (localhost)
**URL**: https://lalten.org/notes

#### Features
- Add shopping list items
- Archive items (moves to "Archived" section)
- Reactivate archived items
- Delete items
- Two-section view: Active Items and Archived Items

#### Database
**File**: `notes.db`
**Table**: `notes`
- `id` (int, primary key)
- `content` (text)
- `created_at` (timestamp)
- `status` (text: 'active' or 'archived')

**Note**: Status column added via migration (ALTER TABLE if not exists)

#### Dependencies
**File**: `requirements.txt`
- FastHTML framework

#### Environment
- Python virtual environment: `.venv/`
- Session key: `.sesskey`

---

## System Architecture

```
Internet (HTTPS:443)
    ↓
nginx (lalten.org)
    ├── / → /var/www/html/index.html (static)
    ├── /menu → localhost:8742 (FastHTML app)
    ├── /notes → localhost:8765 (FastHTML app)
    └── /pages → /root/lalten/pages/ (directory listing)
```

**Note**: All webapps are hosted from `/root/lalten/` as separate directories (e.g., `/root/lalten/menu/`, `/root/lalten/notes/`). Future apps will follow the same pattern.

---

## File Locations Reference

### Configuration Files
- Main nginx config (copy): `/root/lalten/nginx.conf`
- Nginx site configs: `/etc/nginx/sites-available/`
- Enabled sites: `/etc/nginx/sites-enabled/`
- SSL certificates: `/etc/letsencrypt/live/lalten.org/`

### Web Content
- Static root: `/var/www/html/`
- Working directory: `/root/lalten/`
- Menu app: `/root/lalten/menu/`
- Notes app: `/root/lalten/notes/`
- Public pages: `/root/lalten/pages/`

### Databases
- Menu: `/root/lalten/menu/menu.db`
- Notes: `/root/lalten/notes/notes.db`

---

## Process Management

**Status**: Both apps (8742, 8765) are running and responding to requests.

**Management**: Process management method not yet documented (likely systemd service, screen/tmux, or supervisord).

---

## Maintenance Notes

### SSL Certificate Renewal
Certificates are managed by Certbot and should auto-renew. Monitor expiration dates.

### Database Backups
SQLite databases in:
- `/root/lalten/menu/menu.db`
- `/root/lalten/notes/notes.db`

WAL (Write-Ahead Logging) files present, indicating active usage.

### Updates Required
When making changes, update this document and note:
1. Change description
2. Date of change
3. Files affected
4. Any required service restarts

---

## Change Log

| Date | Change | Files Affected |
|------|--------|----------------|
| 2025-10-09 | Initial documentation created | This file |
| 2025-10-09 | Removed dataviz demo app and nginx config | `/etc/nginx/sites-available/dataviz`, `/etc/nginx/sites-enabled/dataviz` |
