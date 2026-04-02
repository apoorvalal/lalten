# jot (vendored deploy copy)

> Upstream project: https://github.com/badlogic/jot
>
> This directory is **not** a traditional GitHub fork. It is a vendored copy of the upstream repository, checked into the `lalten` monorepo so the deployment-specific base-path patch (`/jot`) and server wiring can live alongside the nginx/service config.
>
> If you want the canonical project history, issues, and upstream README context, go to the original source above. The rest of this file is the upstream README content as pulled at deploy time, plus local deployment notes elsewhere in this repo (notably `apps/jot/DEPLOY.md`).

https://github.com/user-attachments/assets/542c333c-c26e-4f04-a5bb-2cf4131e60f3

Minimal self-hosted collaborative markdown editor with inline comment threads. Built for humans and agents.

## Quick Start

```bash
npm install -g @mariozechner/jot
jot serve
```

Open `http://localhost:3210`. Set the owner password on first visit.

## Features

- Collaborative real-time editing (multiple tabs, multiple users)
- Remote cursors with names
- Inline comment threads anchored to text selections
- Threaded replies, resolve/reopen
- Share notes with configurable access (view, comment, edit)
- CLI for humans and agents (owner API keys or share links)
- Agent setup modal with copy-paste instructions
- Dark and light theme
- Mobile support
- `.md` files on disk (derived from collaborative state)

## Server

```bash
npm install -g @mariozechner/jot
jot serve                    # port 3210, data in ./data
jot serve --port=8080        # custom port
jot serve --data=/var/jot    # custom data dir
```

## Docker

```bash
cd docker
bash control.sh start
```

## Sharing

Click the share icon in the editor to configure access:

- **Not shared** (default)
- **View only**: read-only preview
- **View & comment**: preview with comment threads
- **Edit & comment**: full collaborative editor with comments

Each note has a stable share URL (`/s/<id>`). Anyone with the link gets the configured level of access, both in the browser and via the CLI. Toggle access without changing the link.

## CLI

The CLI works in two modes depending on how you register.

### Owner mode

The instance owner creates API keys from the settings gear on the landing page. An API key grants full access to all notes.

```bash
jot register myserver https://jot.example.com <api-key>
jot myserver list
jot myserver search "query"
jot myserver read <note-id>
jot myserver create "My note"
jot myserver edit <note-id> '[{"oldText":"foo","newText":"bar"}]'
jot myserver comment <note-id> "quoted text" "comment body"
jot myserver reply <note-id> <thread-id> <message-id> "reply"
jot myserver resolve <note-id> <thread-id>
jot myserver reopen <note-id> <thread-id>
jot myserver edit-comment <note-id> <message-id> "new body"
jot myserver delete-comment <note-id> <message-id>
jot myserver delete-thread <note-id> <thread-id>
jot myserver update <note-id> title "New title"
jot myserver delete <note-id>
```

### Shared mode

Anyone with a share link can use it to register. No API key needed. The link itself is the credential, and access depends on what the owner configured (view, comment, or edit). This works for both humans and their agents. Humans can use the link in the browser for better UX.

```bash
jot register shared https://jot.example.com/s/abc123
jot shared read
jot shared edit '[{"oldText":"foo","newText":"bar"}]'
jot shared comment "quoted text" "comment body" --name="My Agent"
jot shared reply <thread-id> <message-id> "reply" --name="My Agent"
```

### Agent integration

Click the robot icon in the editor or on a shared note to get copy-paste CLI instructions. The instructions are pre-filled with the instance URL and note ID. Hand them to your agent and it can read, edit, and comment on the note.

## Data

```
data/
  auth.json
  notes/
    <id>.md
    <id>.json
```

The `.md` files are derived from the collaborative editing state stored in the `.json` sidecar. The JSON is the source of truth. The markdown files are written for convenience (grep, backup, external tooling).

## HTTP API

All owner endpoints require `Authorization: Bearer <api-key>`.

| Method | Endpoint                              | Description                         |
| ------ | ------------------------------------- | ----------------------------------- |
| GET    | `/api/notes?q=<query>`                | List/search notes                   |
| POST   | `/api/notes`                          | Create note                         |
| GET    | `/api/notes/:id`                      | Read note                           |
| PUT    | `/api/notes/:id`                      | Update title, markdown, shareAccess |
| DELETE | `/api/notes/:id`                      | Delete note                         |
| POST   | `/api/notes/:id/edit`                 | Apply text edits                    |
| POST   | `/api/notes/:id/threads`              | Create comment thread               |
| POST   | `/api/notes/:id/threads/:tid/replies` | Reply to thread                     |
| PATCH  | `/api/notes/:id/threads/:tid`         | Resolve/reopen thread               |
| DELETE | `/api/notes/:id/threads/:tid`         | Delete thread                       |
| PATCH  | `/api/notes/:id/messages/:mid`        | Edit comment                        |
| DELETE | `/api/notes/:id/messages/:mid`        | Delete comment                      |
| GET    | `/api/keys`                           | List API keys                       |
| POST   | `/api/keys`                           | Create API key                      |
| DELETE | `/api/keys/:id`                       | Delete API key                      |

Share endpoints (no auth, access controlled by `shareAccess`):

| Method | Endpoint                               | Description                    |
| ------ | -------------------------------------- | ------------------------------ |
| GET    | `/api/share/:sid`                      | Read shared note               |
| GET    | `/api/share/:sid/note`                 | Read shared note (lightweight) |
| POST   | `/api/share/:sid/edit`                 | Edit (requires edit access)    |
| POST   | `/api/share/:sid/threads`              | Create comment                 |
| POST   | `/api/share/:sid/threads/:tid/replies` | Reply                          |
| POST   | `/api/share/:sid/render`               | Render markdown to HTML        |

## License

MIT

## Deployment in the lalten monorepo

This deployed copy lives inside the `lalten` monorepo rather than as a traditional Git fork.

### Why it is mounted at `/jot/`
`jot` expects to live at the URL root with root-relative routes such as:
- `/login`
- `/notes/:id`
- `/s/:shareId`
- `/api/...`
- websocket connection on `/`

Because `lalten.org` already hosts other apps, this deployed copy carries a small local base-path patch so it can live under:
- `https://lalten.org/jot/`

That base path is threaded through:
- frontend fetches
- redirects
- asset URLs
- websocket URL construction
- share URLs

### Runtime paths on the Hetzner server
- app source: `/root/lalten/apps/jot`
- persistent data: `/root/lalten/data/jot`
- service file in repo: `/root/lalten/jot.service`
- public URL: `https://lalten.org/jot/`

### Service configuration
The systemd unit runs with:
- `BASE_PATH=/jot`
- `PORT=3210`
- `DATA_DIR=/root/lalten/data/jot`

The unit file is stored in-repo and symlinked into `/etc/systemd/system/`.

### Nginx routing
`/root/lalten/nginx.conf` proxies:
- `/jot/` → `http://127.0.0.1:3210/`
- `/jot` → redirect to `/jot/`

Websocket proxy headers are enabled because `jot` uses `ws` for collaboration.

### Deploy / update procedure
If someone wants to set this up in the same style:

1. sync source into the server repo, e.g. `/root/lalten/apps/jot`
2. make sure Node is available on the server
3. install dependencies:
   ```bash
   npm install
   ```
4. build with the deployment env:
   ```bash
   BASE_PATH=/jot PORT=3210 DATA_DIR=/root/lalten/data/jot npm run build
   ```
5. install a systemd service that starts:
   ```bash
   npm run start
   ```
   with the same env vars
6. add an nginx reverse proxy for `/jot/`
7. validate nginx and restart both nginx + the service

### Minor papercut already fixed
- The note-view back button originally redirected to `/` instead of `/jot/` because one frontend handler in `public/app.js` still used a hardcoded root path.
- Fix: changed it to `withBase("/")`, rebuilt, and restarted the service.

