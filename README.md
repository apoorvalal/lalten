# lalten

Personal website + tiny app host for **lalten.org**.

This repo is the deployment/control plane for the Hetzner box. It contains:
- nginx config
- the repo-controlled landing page
- app source for selected deployed services
- systemd unit files, symlinked into `/etc/systemd/system/`
- static pages under `/root/lalten/pages/`
- in-progress HTML drafts under `/root/lalten/drafts/`
- small app directories under `/root/lalten/<app>/` or `/root/lalten/apps/<app>/`

## Core rule

`/root/lalten/` is the **single source of truth** for deployed app code, nginx config, landing page, and systemd service definitions.

Do **not** hand-edit live copies under `/etc/nginx/...` or `/etc/systemd/system/...` except to maintain symlinks into this repo. Avoid ad-hoc `.bak`, `.old`, or timestamped backup directories; use git for history.

## Current architecture

```text
nginx (HTTPS on lalten.org)
├── /                          -> /root/lalten/index.html
├── /pages/                    -> /root/lalten/pages/
├── /drafts/                   -> /root/lalten/drafts/
├── /misc/                     -> /root/lalten/misc/
├── reverse-proxied app routes -> localhost ports
└── static app aliases         -> app-specific directories
```

## Live routes

### Landing/static aliases
- `/` → `/root/lalten/index.html`
- `/pages/` → `/root/lalten/pages/`
- `/drafts/` → `/root/lalten/drafts/`
- `/misc/` → `/root/lalten/misc/`
- `/galton/` → `/root/lalten/galton/`
- `/chordtutor/` → `/root/lalten/chordtutor/`

### Reverse-proxied apps
- `/notes/` → `127.0.0.1:8765`
- `/menu/` → `127.0.0.1:8742`
- `/linkpull/` → `127.0.0.1:8743`
- `/radio/` and `/proxy` → `127.0.0.1:8750`
- `/parenting/` → `127.0.0.1:8751`
- `/daylight/` → `127.0.0.1:8752`
- `/KrustyTheKrabs/` → `127.0.0.1:8753`
- `/arxiv_methods_charts/` → `127.0.0.1:8754`
- `/pages/regmi_research_papers/api/` → `127.0.0.1:8755`
- `/vega-ui/` → `127.0.0.1:8756`
- `/jot/` → `127.0.0.1:3210`

## Important deployed paths

### Main nginx config
- Repo path: `/root/lalten/nginx.conf`
- Enabled site: `/etc/nginx/sites-enabled/lalten.org` → `/root/lalten/nginx.conf`
- Available site: `/etc/nginx/sites-available/lalten.org` → `/root/lalten/nginx.conf`
- Keep only one enabled nginx site for lalten to avoid duplicate `server_name` warnings.

### Landing page
- Repo path: `/root/lalten/index.html`
- Public URL: `https://lalten.org/`

### Static pages
- Directory: `/root/lalten/pages/`
- Files dropped here are served immediately at `https://lalten.org/pages/<filename>`.
- Current notable artifacts:
  - `/pages/harness_compare_codex_clawd.html`
  - `/pages/lean_crash_course/`
  - `/pages/policy_cate/policy_cate_comparison.html`
  - `/pages/philly-bell.html`
  - `/pages/argminist/`
  - `/pages/econometrica-manuscript/`
  - `/pages/regmi_research_papers/`

### Draft HTML artifacts
- Directory: `/root/lalten/drafts/`
- Use for in-progress, self-contained HTML drafts that Krabbs should publish and link for review.
- Files dropped here are served immediately at `https://lalten.org/drafts/<filename>.html`.

### Jot
- App source: `/root/lalten/apps/jot`
- Persistent data: `/root/lalten/data/jot`
- Service file in repo: `/root/lalten/jot.service`
- Public URL: `https://lalten.org/jot/`
- Local bind: `127.0.0.1:3210`
- Notes:
  - This is a vendored deploy copy of upstream `https://github.com/badlogic/jot`.
  - It is **not** a traditional GitHub fork.
  - It has local base-path support for `/jot/` and KaTeX-enabled previews.
  - See `apps/jot/DEPLOY.md` if present and `apps/jot/README.md`.

### Vega UI
- App source: `/root/lalten/apps/vega-ui`
- Service file in repo: `/root/lalten/vega-ui.service`
- Public URL: `https://lalten.org/vega-ui/`
- Local bind: `127.0.0.1:8756`
- Notes:
  - Vendored from `https://github.com/apoorvalal/vega-ui` at deploy time.
  - It runs with `VEGA_UI_BASE_PATH=/vega-ui`.

### Regmi research search
- Static papers/index: `/root/lalten/pages/regmi_research_papers/`
- Backend app: `/root/lalten/regmi_search`
- Public search API path: `/pages/regmi_research_papers/api/`
- Service file in repo: `/root/lalten/regmi_search/regmi_search.service`

## Systemd unit rule

All lalten webapp units live in this repo and are symlinked from `/etc/systemd/system/`:

- `/etc/systemd/system/notes.service` → `/root/lalten/notes/notes.service`
- `/etc/systemd/system/menu.service` → `/root/lalten/menu/menu.service`
- `/etc/systemd/system/linkpull.service` → `/root/lalten/linkpull/linkpull.service`
- `/etc/systemd/system/radio.service` → `/root/lalten/radio/radio.service`
- `/etc/systemd/system/parenting.service` → `/root/lalten/parenting/parenting.service`
- `/etc/systemd/system/daylight.service` → `/root/lalten/daylight/daylight.service`
- `/etc/systemd/system/arxiv_ranker.service` → `/root/lalten/arxiv_ranker/arxiv_ranker.service`
- `/etc/systemd/system/krustythekrabs.service` → `/root/lalten/krustythekrabs/krustythekrabs.service`
- `/etc/systemd/system/regmi_search.service` → `/root/lalten/regmi_search/regmi_search.service`
- `/etc/systemd/system/vega-ui.service` → `/root/lalten/vega-ui.service`
- `/etc/systemd/system/jot.service` → `/root/lalten/jot.service`

## Deployment patterns

### Static page/app
Use this for one-file or mostly-static HTML/JS/CSS projects.

- Put stable public artifacts under `/root/lalten/pages/`, or
- put in-progress review drafts under `/root/lalten/drafts/`, or
- create an app directory under `/root/lalten/<app>/` and add an nginx alias route for a dedicated path.

No service restart is needed for plain `/pages/` or `/drafts/` content.

### Reverse-proxied app
Use this for FastHTML, Streamlit, Node, or other long-running services.

General pattern:
1. add app code under `/root/lalten/<app>/` or `/root/lalten/apps/<app>/`
2. add a service file **in this repo**
3. symlink the service file into `/etc/systemd/system/`
4. add an nginx location block in `/root/lalten/nginx.conf`
5. run `nginx -t`
6. restart/reload nginx and the service

### Data directories
Persistent state should generally live outside the app working tree when convenient, e.g. `/root/lalten/data/<app>/`. The repo ignores `/data/jot/`.

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
2. document deployment-specific details in the relevant app subdirectory when useful, and
3. commit the config/source/docs together unless Apoorva asks otherwise.

## Notes on assistant-managed deploys

Krabbs can:
- add static pages to `/pages/`
- add in-progress self-contained HTML drafts to `/drafts/` and send `https://lalten.org/drafts/<filename>.html`
- deploy small Python/Node apps behind nginx
- maintain repo-local nginx + service definitions

Every deploy should leave behind documentation in this repo so the server state stays legible to future humans and future Krabbs.
