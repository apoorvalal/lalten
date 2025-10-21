# Web Radio Player - Implementation Plan

## Design Philosophy

**Ultra-lean web interface** that streams radio stations directly to client browsers (including mobile phones). The server handles playlist parsing and station metadata, while HTML5 `<audio>` element handles playback on the client side.

## Architecture

### Process Model
```
┌─────────────────────────────────────────────────┐
│  Client Browser (Mobile/Desktop)                │
│  - HTML5 <audio> element plays stream           │
│  - Controls: play/stop/change station           │
│  - Receives stream URL from server              │
└─────────────────────────────────────────────────┘
                    │
                    ├── HTTP(S) requests
                    ↓
┌─────────────────────────────────────────────────┐
│  FastHTML Web App (port 8750)                   │
│  - Serves station list & metadata               │
│  - Resolves .pls/.m3u URLs to direct streams    │
│  - Tracks user state (current station)          │
│  - No audio processing on server!               │
└─────────────────────────────────────────────────┘
```

**Key Insight**:
- HTML5 `<audio>` can play most direct stream URLs (mp3, aac streams)
- For `.pls`/`.m3u` playlist files, server **parses** them and extracts the actual stream URL
- Client browser does all the heavy lifting (decoding, playback)
- Server is stateless (no background processes needed!)

### Data Model

**SQLite Database** (`radio.db`):
```sql
CREATE TABLE stations (
    name TEXT PRIMARY KEY,
    url TEXT NOT NULL,           -- original URL (may be .pls/.m3u)
    stream_url TEXT,             -- resolved direct stream URL (cached)
    category TEXT,               -- 'KEXP', 'SOMA', 'Bluemars', etc.
    description TEXT,
    last_checked TEXT            -- timestamp of last URL resolution
);
```

**State**: Stored in client browser (current station, playing/stopped). Server is stateless!

**Initial setup**: Pre-populate `stations` table from `stations.txt`, resolve playlist URLs once at startup.

### Web UI (Single Page)

```
┌─────────────────────────────────────────────────┐
│  🎵 Web Radio Player                            │
├─────────────────────────────────────────────────┤
│  Now Playing: [KEXP - Seattle]                  │
│  🔊 ━━━━━━━━━━━━━━━━━━━━ [||] [🔄]            │
│                                                 │
│  Volume: [▬▬▬▬▬▬▬▬▬▬░░░░░]                     │
├─────────────────────────────────────────────────┤
│  Stations:                                      │
│                                                 │
│  📻 KEXP          [▶]                           │
│  📻 KCRW          [▶]                           │
│  📻 KNKX Jazz     [▶]                           │
│  📻 SOMAGroove    [▶]                           │
│  📻 SOMASpace     [▶]                           │
│  📻 BLUE Mars     [▶]                           │
│  ...                                            │
│                                                 │
│  [🎲 Random Station]                            │
└─────────────────────────────────────────────────┘
```

**Features**:
- HTML5 `<audio>` element (hidden) for playback
- Play/pause controls
- Volume slider
- Station list with play buttons
- Currently playing station highlighted
- Random station picker
- Mobile-friendly (works on phone!)
- Pure HTML/CSS + minimal vanilla JS (no frameworks needed)

## Implementation Steps

### 1. Playlist Parser Module (`playlist_parser.py`)

```python
import requests
import re

def parse_playlist_url(url):
    """
    Parse .pls or .m3u playlist files and return direct stream URL.
    If URL is already a direct stream, return as-is.
    """
    if not (url.endswith('.pls') or url.endswith('.m3u')):
        return url  # Already a direct stream URL

    try:
        response = requests.get(url, timeout=10)
        content = response.text

        if url.endswith('.pls'):
            # PLS format: File1=http://stream.url
            match = re.search(r'File\d+=(.+)', content)
            if match:
                return match.group(1).strip()

        elif url.endswith('.m3u'):
            # M3U format: Lines starting with http/https
            for line in content.splitlines():
                line = line.strip()
                if line.startswith('http'):
                    return line

        # Fallback: return original URL
        return url

    except Exception as e:
        print(f"Error parsing playlist {url}: {e}")
        return url  # Return original on error
```

### 2. Database Setup (`db_setup.py`)

```python
from fasthtml.common import *
import json
from pathlib import Path
from playlist_parser import parse_playlist_url

def init_db():
    db = database('radio.db')

    # Stations table
    stations = db.t.stations
    if stations not in db.t:
        stations.create(
            name=str,
            url=str,
            stream_url=str,
            category=str,
            description=str,
            last_checked=str,
            pk='name'
        )
        # Load from stations.txt
        script_dir = Path(__file__).parent
        with open(script_dir / 'stations.txt') as f:
            station_data = json.load(f)

        print("Resolving playlist URLs...")
        for name, url in station_data.items():
            # Categorize by prefix
            if name.startswith('SOMA'):
                category = 'SomaFM'
            elif name in ['BLUE', 'CRYO', 'VOWI']:
                category = 'Bluemars'
            else:
                category = 'Other'

            # Resolve playlist URLs to direct streams
            stream_url = parse_playlist_url(url)
            print(f"  {name}: {url} -> {stream_url}")

            stations.insert(
                name=name,
                url=url,
                stream_url=stream_url,
                category=category,
                description=name,
                last_checked=None
            )

    return db
```

### 3. Main Application (`main.py`)

```python
from fasthtml.common import *
from db_setup import init_db
import random

# Initialize
db = init_db()
stations_table = db.t.stations

app, rt = fast_app()

# Embedded JavaScript for audio control
audio_js = """
<script>
let currentStation = null;
const audio = document.getElementById('radioPlayer');
const nowPlaying = document.getElementById('nowPlaying');

function playStation(name, url) {
    currentStation = name;
    audio.src = url;
    audio.play();
    nowPlaying.textContent = 'Now Playing: ' + name;

    // Highlight current station
    document.querySelectorAll('.station-btn').forEach(btn => {
        btn.style.backgroundColor = '#6c757d';
    });
    event.target.style.backgroundColor = '#007bff';
}

function pauseRadio() {
    audio.pause();
    nowPlaying.textContent = 'Paused: ' + currentStation;
}

function resumeRadio() {
    if (currentStation) {
        audio.play();
        nowPlaying.textContent = 'Now Playing: ' + currentStation;
    }
}

// Update play/pause button based on audio state
audio.addEventListener('play', () => {
    document.getElementById('pauseBtn').textContent = '⏸️ Pause';
});
audio.addEventListener('pause', () => {
    document.getElementById('pauseBtn').textContent = '▶️ Resume';
});
</script>
"""

@rt('/')
def get():
    all_stations = list(stations_table())

    # Hidden audio element
    audio_player = Audio(
        id='radioPlayer',
        controls=False,  # Hide default controls
        style='display: none;'
    )

    # Now playing status
    status_div = Div(
        H2(id='nowPlaying', style='color: #007bff; margin: 10px 0;')('Select a station'),
        Div(
            Button('⏸️ Pause',
                   id='pauseBtn',
                   onclick='audio.paused ? resumeRadio() : pauseRadio()',
                   style='padding: 10px 20px; background-color: #28a745; color: white; border: none; cursor: pointer; font-size: 1em; margin: 10px 5px;'),
            Input(type='range',
                  min='0', max='100', value='80',
                  oninput='audio.volume = this.value / 100',
                  style='width: 200px; vertical-align: middle; margin: 0 10px;'),
            style='margin: 10px 0;'
        ),
        style='padding: 20px; border: 1px solid #ddd; border-radius: 5px; margin-bottom: 20px; background-color: #f9f9f9; text-align: center;'
    )

    # Station list
    station_list = []
    for station in all_stations:
        station_list.append(
            Div(
                Span(f'📻 {station.name}',
                     style='font-weight: bold; flex: 1;'),
                Button('▶️',
                       cls='station-btn',
                       onclick=f"playStation('{station.name}', '{station.stream_url}')",
                       style='padding: 8px 16px; background-color: #6c757d; color: white; border: none; cursor: pointer; margin-left: 10px;'),
                style='display: flex; align-items: center; padding: 12px; margin: 8px 0; border: 1px solid #ddd; border-radius: 5px; background-color: #fff;'
            )
        )

    # Random button
    random_stations_json = [{
        'name': s.name,
        'url': s.stream_url
    } for s in all_stations]

    random_btn = Button(
        '🎲 Play Random Station',
        onclick=f'''
            const stations = {random_stations_json};
            const station = stations[Math.floor(Math.random() * stations.length)];
            playStation(station.name, station.url);
        ''',
        style='padding: 12px 24px; background-color: #17a2b8; color: white; border: none; cursor: pointer; font-size: 1.1em; margin: 20px 0; width: 100%;'
    )

    return Titled('🎵 Web Radio Player',
        audio_player,
        status_div,
        H3('Stations'),
        Div(*station_list),
        random_btn,
        Script(audio_js),
        style='max-width: 600px; margin: 0 auto; padding: 20px; font-family: Arial, sans-serif;'
    )

serve(host='0.0.0.0', port=8750)
```

## Advantages of This Approach

1. **Client-side playback**: Audio plays in browser (mobile phone, desktop, anywhere!)
2. **Stateless server**: No background processes, very lightweight
3. **Playlist resolution**: Server pre-parses .pls/.m3u files once, caches direct URLs
4. **HTML5 native**: Uses standard `<audio>` element, works everywhere
5. **Mobile-friendly**: Works on phones via mobile browser
6. **Multi-user**: Multiple people can listen simultaneously (each browser streams independently)
7. **Simple code**: ~100 lines of Python + minimal vanilla JS

## How It Works

1. **Startup**: Server parses all playlist URLs from `stations.txt`, extracts direct stream URLs
2. **User visits page**: Server sends station list with resolved stream URLs
3. **User clicks play**: JavaScript sets `audio.src` and calls `audio.play()`
4. **Browser streams**: Client browser connects directly to radio stream and plays audio
5. **Server does nothing**: No server involvement in audio streaming!

## Port Assignment

**Port 8750** - Next available in sequence (8742, 8765, 8750)

## Testing Plan

1. Test playlist parsing manually:
   ```python
   from playlist_parser import parse_playlist_url

   # Test .pls file
   url = parse_playlist_url('https://somafm.com/nossl/groovesalad256.pls')
   print(url)

   # Test .m3u file
   url = parse_playlist_url('http://streams.echoesofbluemars.org:8000/bluemars.m3u')
   print(url)

   # Test direct URL
   url = parse_playlist_url('https://kexp-mp3-128.streamguys1.com/kexp128.mp3')
   print(url)
   ```

2. Test HTML5 audio with resolved URLs in browser console:
   ```javascript
   const audio = new Audio('http://resolved-stream-url');
   audio.play();
   ```

3. Test on mobile phone browser (Safari/Chrome)

4. Build and test web UI incrementally

## Future Enhancements (Optional)

- Station favorites/recently played (store in browser localStorage)
- Custom station URLs (input field to add temporary stations)
- Now playing metadata extraction (Icecast/Shoutcast streams provide this via headers)
- Sleep timer (stop after X minutes)
- Equalizer/audio effects (Web Audio API)
- Per-user persistent state (login/sessions to remember last station)
- Genre categorization/filtering

## Mobile Considerations

- **HTTPS required**: Modern mobile browsers require HTTPS for audio playback (you have Let's Encrypt!)
- **User gesture**: iOS Safari requires user interaction (button click) before playing audio - already handled!
- **Background playback**: iOS supports background audio for streaming URLs
- **Data usage**: Direct streaming uses cellular data - users should be aware
- **Autoplay policies**: Some browsers block autoplay - require explicit play button (already designed this way)
