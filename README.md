# lalten

Personal website + tiny app host for **lalten.org**.

This repo is the deployment/control plane for the Hetzner box. It contains:
- nginx config
- app source for selected deployed services
- systemd unit files (kept in-repo, symlinked into `/etc/systemd/system/`)
- static pages under `/root/lalten/pages/`
- small app directories under `/root/lalten/<app>/` or `/root/lalten/apps/<app>/`

## Core rule

`/root/lalten/` is the **single source of truth** for deployed app code, nginx config, and systemd service definitions.

Do **not** hand-edit live copies under `/etc/nginx/...` or `/etc/systemd/system/...` except to maintain symlinks into this repo.

## Current architecture

At a high level:

```text
nginx (HTTPS on lalten.org)
├── static root                -> /var/www/html
├── /pages/                    -> /root/lalten/pages/
├── /misc/                     -> /root/lalten/misc/
├── reverse-proxied app routes -> localhost ports
└── static app aliases         -> app-specific directories
```

## Live routes

### Static / alias-backed
- `/pages/` → `/root/lalten/pages/`
- `/misc/` → `/root/lalten/misc/`
- `/galton/` → static app in `/root/lalten/galton/`
- `/chordtutor/` → static app in `/root/lalten/chordtutor/`

### Reverse-proxied apps
- `/notes/` → `127.0.0.1:8765`
- `/menu/` → `127.0.0.1:8742`
- `/linkpull/` → `127.0.0.1:8743`
- `/radio/` and `/proxy` → `127.0.0.1:8750`
- `/parenting` → `127.0.0.1:8751`
- `/daylight/` → `127.0.0.1:8752`
- `/KrustyTheKrabs/` → `127.0.0.1:8753`
- `/arxiv_methods_charts/` → `127.0.0.1:8754`
- `/pages/regmi_research_papers/api/` → `127.0.0.1:8755`
- `/jot/` → `127.0.0.1:3210`

## Important deployed paths

### Main nginx config
- Repo path: `/root/lalten/nginx.conf`
- System path should be a symlink target from nginx's enabled site config.

### Static pages
- Directory: `/root/lalten/pages/`
- Files dropped here are served immediately at:
  - `https://lalten.org/pages/<filename>`

### Jot
- App source: `/root/lalten/apps/jot`
- Persistent data: `/root/lalten/data/jot`
- Service file in repo: `/root/lalten/jot.service`
- Public URL: `https://lalten.org/jot/`
- Notes:
  - This is a vendored deploy copy of upstream `https://github.com/badlogic/jot`
  - It is **not** a traditional GitHub fork
  - It has a local base-path patch so it can live under `/jot/`
  - See `apps/jot/DEPLOY.md`

### Regmi research search
- Backend app: `/root/lalten/regmi_search`
- Public search API path: `/pages/regmi_research_papers/api/`

## Deployment patterns

### 1. Static page/app
Use this for one-file or mostly-static HTML/JS/CSS projects.

- Put assets under `/root/lalten/pages/` for simple static publishing, or
- create an app directory under `/root/lalten/<app>/` and add an nginx alias route if you want a dedicated prettier path.

No service restart is needed for plain `/pages/` content.

### 2. Reverse-proxied app
Use this for FastHTML, Streamlit, Node, or other long-running services.

General pattern:
1. add app code under `/root/lalten/<app>/` or `/root/lalten/apps/<app>/`
2. add a service file **in this repo**
3. symlink the service file into `/etc/systemd/system/`
4. add an nginx location block in `/root/lalten/nginx.conf`
5. run `nginx -t`
6. restart/reload nginx and the service

### 3. Data directories
Persistent state should generally live outside the app working tree when convenient, e.g.
- `/root/lalten/data/<app>/`

This keeps updates cleaner and makes backup policy more obvious.

## Services and operations

### Inspect service status
```bash
systemctl status <service>.service
```

### Follow logs
```bash
journalctl -u <service>.service -f
```

### Restart after code changes
```bash
systemctl restart <service>.service
```

### Validate and reload nginx
```bash
nginx -t
systemctl reload nginx
```

## Documentation rule for future deploys

Whenever a **new app or deployment path** is added to this server:
1. update this root `README.md` to mention it,
2. document deployment-specific details in the relevant app subdirectory (for example `DEPLOY.md`), and
3. **ask Apoorva whether to commit/push**, rather than silently assuming that part.

## Notes on assistant-managed deploys

Krabbs can:
- add static pages to `/pages/`
- deploy small Python/Node apps behind nginx
- maintain repo-local nginx + service definitions
- publish digest-like artifacts to KrustyTheKrabs

But every new deploy should leave behind documentation in this repo so the server state stays legible to future humans and future Krabbs.
