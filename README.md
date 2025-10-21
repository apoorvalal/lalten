# lalten
bare metal website repo. High-level steps for setup: 

1. get a small vps (~raspberry pi housed in some rural shed). Hetzner's go for the price of a coffee.
2. (optional) buy a domain on namecheap and point the VPS's IP address at the domain.
3. host index.html and webapps on the VPS and access it either via the ip address or the domain name. For example, check out my radio player at [this](https://lalten.org/radio) link. 

## Architecture

Personal/family website at **lalten.org** hosting static pages and FastHTML web applications. Each app is a self-contained, single-file Python application served via nginx reverse proxy.

### Deployment Pattern

```
nginx (443/HTTPS) → Path-based routing
├── /           → Static landing page (/var/www/html/index.html)
├── /pages/     → Static file directory (/root/lalten/pages/)
├── /menu       → FastHTML app (port 8742) - Menu planner
├── /notes      → FastHTML app (port 8765) - Note-taking app
├── /radio      → FastHTML app (port 8750) - Web radio player with streaming proxy
└── /proxy      → Radio streaming endpoint (proxies to port 8750)
```

## Generalized Recipe for New CRUD Apps

### 1. Create App Directory Structure

```bash
mkdir /root/lalten/<app_name>
cd /root/lalten/<app_name>
python3 -m venv .venv
source .venv/bin/activate
pip install python-fasthtml
pip freeze > requirements.txt
```

### 2. Write `main.py` (Template)

```python
from fasthtml.common import *

# Initialize database
db = database('<app_name>.db')
items = db.t.items
if items not in db.t:
    items.create(id=int, content=str, created_at=str, pk='id')
Item = items.dataclass()

# Create app
app, rt = fast_app()

@rt('/')
def get():
    all_items = items(order_by='id DESC')

    form = Form(
        Textarea(name='content', placeholder='Enter item...', rows=4,
                style='width: 100%; padding: 8px; margin-bottom: 10px;'),
        Button('Add Item', type='submit',
               style='padding: 8px 16px; background-color: #007bff; color: white; border: none; cursor: pointer;'),
        method='post', action='/<app_name>/add', style='width: 100%;'
    )

    items_list = Div(
        *[Div(
            P(Strong(f"Item #{item.id}"), style='margin: 0; color: #666; font-size: 0.9em;'),
            P(item.content, style='margin: 10px 0;'),
            Div(
                Form(Button('Delete', type='submit',
                           style='padding: 4px 12px; background-color: #dc3545; color: white; border: none; cursor: pointer;'),
                    method='post', action=f'/<app_name>/delete/{item.id}', style='display: inline;'),
                style='display: flex; gap: 8px;'
            ),
            style='border: 1px solid #ddd; padding: 15px; margin-bottom: 15px; border-radius: 5px; background-color: #f9f9f9;'
        ) for item in all_items],
        style='margin-top: 20px;'
    )

    return Titled('App Title', form, items_list,
                 style='max-width: 1000px; margin: 0 auto; padding: 20px; font-family: Arial, sans-serif;')

@rt('/add', methods=['post'])
def post(content: str):
    from datetime import datetime
    if content.strip():
        items.insert(content=content, created_at=datetime.now().isoformat())
    return RedirectResponse('/<app_name>', status_code=303)

@rt('/delete/{item_id}', methods=['post'])
def delete(item_id: int):
    items.delete(item_id)
    return RedirectResponse('/<app_name>', status_code=303)

serve(host='0.0.0.0', port=<unique_port>)
```

### 3. Create Systemd Service

Create `<app_name>.service` file in the app directory:

```ini
[Unit]
Description=<App Name> Web Application
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/lalten/<app_name>
ExecStart=/usr/bin/uv run python /root/lalten/<app_name>/main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Symlink and enable:
```bash
# Create symlink (keeps service file in git repo)
sudo ln -s /root/lalten/<app_name>/<app_name>.service /etc/systemd/system/<app_name>.service

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable <app_name>.service
sudo systemctl start <app_name>.service
```

### 4. Configure Nginx

Add to `/etc/nginx/sites-available/lalten.org` (inside the main server block):

```nginx
location /<app_name>/ {
    proxy_pass http://127.0.0.1:<port>/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}

location = /<app_name> {
    proxy_pass http://127.0.0.1:<port>/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

Reload nginx:
```bash
nginx -t
systemctl reload nginx
```

### 5. Port Allocation

- `8742` - menu app
- `8750` - radio app
- `8765` - notes app
- `87XX` - future apps (choose next available)

## Tech Stack

- **Framework**: FastHTML (Python web framework with HTMX)
- **Database**: SQLite with FastHTML ORM helpers
- **Styling**: Pico CSS (CDN) + inline styles
- **Server**: Nginx reverse proxy
- **Process Management**: systemd services
