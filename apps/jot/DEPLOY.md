# Jot deployment notes

This app is deployed under `https://lalten.org/jot/`.

## Why it is mounted at `/jot/`
`jot` expects to live at the URL root (`/`) with root-relative routes for:
- `/login`
- `/notes/:id`
- `/s/:shareId`
- `/api/...`
- websocket connection on `/`

Because `lalten.org` already serves other apps, this deploy patches `jot` to respect:
- `BASE_PATH=/jot`

That base path is threaded through:
- frontend fetches
- redirects
- asset URLs
- websocket URL construction
- share URLs

## Runtime
- App path: `/root/lalten/apps/jot`
- Data path: `/root/lalten/data/jot`
- Service file: `/root/lalten/jot.service`
- Port: `3210`
- Node runtime: `/root/.nvm/versions/node/v22.20.0/bin`

## Service
Systemd unit:
- `/etc/systemd/system/jot.service` (symlink to `/root/lalten/jot.service`)

Important environment variables:
- `BASE_PATH=/jot`
- `PORT=3210`
- `DATA_DIR=/root/lalten/data/jot`

## Nginx
The nginx config in `/root/lalten/nginx.conf` proxies:
- `/jot/` -> `http://127.0.0.1:3210/`
- `/jot` -> redirect to `/jot/`

Websocket proxy headers are enabled because `jot` uses `ws` for collaboration.

## Deploy / update procedure
From a trusted machine:
1. sync source into `/root/lalten/apps/jot`
2. run `npm install`
3. run `BASE_PATH=/jot PORT=3210 DATA_DIR=/root/lalten/data/jot npm run build`
4. `systemctl restart jot`
5. `systemctl restart nginx`

## First startup
Visiting `/jot/` initially lands on `Set password`.
That sets the owner password for the instance.
