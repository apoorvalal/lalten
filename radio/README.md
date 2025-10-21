# Web Radio Player

A FastHTML-based web radio player with streaming proxy support, accessible at [lalten.org/radio](https://lalten.org/radio). Features preset stations (KEXP, SomaFM, KCRW) and custom stream support for MP3, PLS, and M3U URLs.

## Features

- HTML5 audio playback with streaming proxy
- Add/delete custom stations
- Playlist parsing (.pls, .m3u files)
- Random station selector
- Debug console for troubleshooting
- Persistent SQLite database

## Web App Deployment

The web app runs on port 8750 and is accessible at `/radio` via nginx reverse proxy. Key configuration:

- **Nginx streaming proxy** at `/proxy` with `proxy_buffering off` for proper audio streaming
- **CORS headers** for HTML5 audio cross-origin support
- **Database**: SQLite (`radio.db`) with stations table using `name` as primary key
- **Routes**:
  - `GET /` - Main radio interface
  - `POST /radio/add_station` - Add new station
  - `POST /radio/delete/{station_name}` - Delete station
  - `GET /proxy?url=<stream_url>` - Streaming proxy endpoint

See main repo README for systemd service setup.

---

## Terminal Version (`termradio.py`)

A simple, bare-bones terminal radio player with an opinionated set of default stations.

### Usage

```{python}
python3 termradio.py SOMAGroove
```

If you make the script executable [`chmod +x termradio.py`], you can drop the extension and run

```
./termradio KEXP
```

If you store the script somewhere in your `$PATH` (e.g. `$HOME/.local/bin`), you can run `termradio <station>` from anywhere, or execute it as a background process from a launcher.

`termradio` accepts 1 argument, which is either a station name in
`stations.txt`, or a streaming url.

Stations live in a dictionary `stations.txt`, which is
pre-populated with a few stations I like (KEXP, KCRW, SOMAFM), and can
be added to by the user (please maintain valid python dict syntax). Send me pull requests (that double up as music recommendations, for once).


Play a random station:
```bash
python termradio.py
```

Play a specific station from `stations.txt`:
```bash
python termradio.py <station_name>
```
Example: `python termradio.py classic-rock-florida`

Play a stream from a URL:
```bash
python termradio.py <url>
```

## Supported Players

This script supports `mpv`, `mplayer`, and `vlc`. It will automatically detect which player you have installed. `mpv` is recommended.

## Installation of mpv

Here's how to install `mpv` on different operating systems.

### macOS (using Homebrew)

```bash
brew install mpv
```

### Ubuntu/Debian

```bash
sudo apt update
sudo apt install mpv
```

### Arch Linux

```bash
sudo pacman -Syu mpv
```

### Windows (using Scoop)

First, install [Scoop](https://scoop.sh/) if you don't have it. Then run:
```bash
scoop install mpv
```

