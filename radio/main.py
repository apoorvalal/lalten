from fasthtml.common import *
from starlette.responses import RedirectResponse
from db_setup import init_db
from playlist_parser import parse_playlist_url
import json
import urllib.parse

# Initialize
db = init_db()
stations_table = db.t.stations

app, rt = fast_app()

# Embedded JavaScript using native HTML5 Audio
audio_js = """
let currentStation = null;
let audio = null;
const nowPlaying = document.getElementById('nowPlaying');
const debugLog = document.getElementById('debugLog');

function log(message, isError = false) {
    const timestamp = new Date().toLocaleTimeString();
    const line = document.createElement('div');
    line.style.color = isError ? '#dc3545' : '#666';
    line.style.fontSize = '0.85em';
    line.style.borderBottom = '1px solid #eee';
    line.style.padding = '4px 0';
    line.textContent = `[${timestamp}] ${message}`;
    debugLog.insertBefore(line, debugLog.firstChild);

    // Keep only last 20 messages
    while (debugLog.children.length > 20) {
        debugLog.removeChild(debugLog.lastChild);
    }
}

function playStation(name, url) {
    currentStation = name;
    log(`Attempting to play: ${name}`);
    log(`Stream URL: ${url}`);

    // Stop current audio if playing
    if (audio) {
        audio.pause();
        audio.src = '';
        log('Stopped previous stream');
    }

    // Create new Audio element
    audio = new Audio();
    audio.crossOrigin = 'anonymous';
    audio.preload = 'none';
    audio.volume = 0.8;

    // Event listeners
    audio.addEventListener('loadstart', () => log('Loading stream...'));
    audio.addEventListener('canplay', () => log('✓ Stream ready to play'));
    audio.addEventListener('playing', () => {
        log('✓ Playback started');
        nowPlaying.textContent = 'Now Playing: ' + name;
        document.getElementById('pauseBtn').textContent = '⏸️ Pause';
    });
    audio.addEventListener('pause', () => {
        log('Paused');
        document.getElementById('pauseBtn').textContent = '▶️ Resume';
    });
    audio.addEventListener('error', (e) => {
        const errorMessages = [
            'Unknown error',
            'MEDIA_ERR_ABORTED: Playback aborted',
            'MEDIA_ERR_NETWORK: Network error',
            'MEDIA_ERR_DECODE: Decode error',
            'MEDIA_ERR_SRC_NOT_SUPPORTED: Format not supported'
        ];
        const errorMsg = errorMessages[audio.error?.code || 0] || 'Unknown error';
        log(`✗ Error: ${errorMsg}`, true);
        nowPlaying.textContent = 'Error: ' + name;
    });
    audio.addEventListener('stalled', () => log('Stream stalled (buffering...)', false));
    audio.addEventListener('waiting', () => log('Buffering...', false));
    audio.addEventListener('progress', () => log('Downloading stream data...', false));

    // Set source and play
    audio.src = url;
    audio.load();

    // Attempt to play (might be blocked by autoplay policy)
    const playPromise = audio.play();
    if (playPromise !== undefined) {
        playPromise
            .then(() => log('✓ Play request successful'))
            .catch(error => {
                log(`✗ Play blocked: ${error.message} (click play again)`, true);
            });
    }

    // Highlight current station
    document.querySelectorAll('.station-btn').forEach(btn => {
        btn.style.backgroundColor = '#6c757d';
    });
    event.target.style.backgroundColor = '#007bff';
}

function pauseRadio() {
    if (audio) {
        if (!audio.paused) {
            audio.pause();
            nowPlaying.textContent = 'Paused: ' + currentStation;
        } else {
            audio.play()
                .then(() => {
                    nowPlaying.textContent = 'Now Playing: ' + currentStation;
                })
                .catch(error => log(`✗ Resume error: ${error.message}`, true));
        }
    }
}

function setVolume(value) {
    if (audio) {
        audio.volume = value / 100;
        log(`Volume set to ${value}%`);
    }
}

log('Radio player initialized (HTML5 Audio)');
"""

@rt('/proxy')
async def proxy_stream(url: str):
    """Proxy audio streams to handle HTTP sources and playlist files."""
    from starlette.responses import StreamingResponse
    import httpx

    # Resolve playlist URLs to direct stream URLs
    resolved_url = parse_playlist_url(url)

    async def stream_audio():
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream('GET', resolved_url) as response:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    yield chunk

    return StreamingResponse(
        stream_audio(),
        media_type='audio/mpeg',
        headers={
            'Cache-Control': 'no-cache',
            'Accept-Ranges': 'none',
        }
    )

@rt('/add_station')
def post(name: str, url: str):
    """Add a new station to the database."""
    # Store the original URL (don't resolve yet - let proxy handle it)
    stations_table.insert({
        'name': name,
        'stream_url': url
    })

    # Redirect back to home
    return RedirectResponse('/', status_code=303)

@rt('/')
def get():
    all_stations = list(stations_table())

    # Now playing status
    status_div = Div(
        H2(id='nowPlaying', style='color: #007bff; margin: 10px 0;')('Select a station'),
        Div(
            Button('⏸️ Pause',
                   id='pauseBtn',
                   onclick='pauseRadio()',
                   style='padding: 10px 20px; background-color: #28a745; color: white; border: none; cursor: pointer; font-size: 1em; margin: 10px 5px;'),
            Input(type='range',
                  min='0', max='100', value='80',
                  oninput='setVolume(this.value)',
                  style='width: 200px; vertical-align: middle; margin: 0 10px;'),
            style='margin: 10px 0;'
        ),
        style='padding: 20px; border: 1px solid #ddd; border-radius: 5px; margin-bottom: 20px; background-color: #f9f9f9; text-align: center;'
    )

    # Debug console
    debug_div = Details(
        Summary('🐛 Debug Console', style='cursor: pointer; font-weight: bold; padding: 10px; background-color: #f0f0f0; border-radius: 5px;'),
        Div(id='debugLog',
            style='max-height: 300px; overflow-y: auto; padding: 10px; background-color: #fafafa; border: 1px solid #ddd; border-radius: 5px; margin-top: 10px; font-family: monospace;'),
        style='margin-bottom: 20px;'
    )

    # Custom URL input
    custom_input = Div(
        H3('Add Custom Stream'),
        Form(
            Input(type='text',
                  name='name',
                  id='customName',
                  placeholder='Station name (e.g., "My Favorite Station")',
                  style='width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 5px;'),
            Input(type='text',
                  name='url',
                  id='customUrl',
                  placeholder='Paste stream URL (e.g., http://example.com/stream.mp3 or .pls/.m3u)',
                  style='width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 5px;'),
            Div(
                Button('▶️ Play',
                       type='button',
                       onclick="playStation(document.getElementById('customName').value || 'Custom Stream', '/proxy?url=' + encodeURIComponent(document.getElementById('customUrl').value))",
                       style='padding: 10px 20px; background-color: #6c757d; color: white; border: none; cursor: pointer; flex: 1; margin-right: 10px;'),
                Button('💾 Save',
                       type='submit',
                       style='padding: 10px 20px; background-color: #28a745; color: white; border: none; cursor: pointer; flex: 1;'),
                style='display: flex; gap: 10px;'
            ),
            action='/add_station',
            method='post'
        ),
        style='margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; background-color: #f9f9f9;'
    )

    # Station list
    station_list = []
    for station in all_stations:
        station_name = station['name'] if isinstance(station, dict) else station.name
        station_url = station['stream_url'] if isinstance(station, dict) else station.stream_url

        # Always use proxy (handles playlists and HTTP/HTTPS conversion)
        play_url = f'/proxy?url={urllib.parse.quote(station_url)}'

        station_list.append(
            Div(
                Span(f'📻 {station_name}',
                     style='font-weight: bold; flex: 1;'),
                Button('▶️',
                       cls='station-btn',
                       onclick=f"playStation('{station_name}', '{play_url}')",
                       style='padding: 8px 16px; background-color: #6c757d; color: white; border: none; cursor: pointer; margin-left: 10px;'),
                style='display: flex; align-items: center; padding: 12px; margin: 8px 0; border: 1px solid #ddd; border-radius: 5px; background-color: #fff;'
            )
        )

    # Random button - convert stations to JSON
    random_stations_json = json.dumps([{
        'name': s['name'] if isinstance(s, dict) else s.name,
        'url': s['stream_url'] if isinstance(s, dict) else s.stream_url
    } for s in all_stations])

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
        status_div,
        debug_div,
        custom_input,
        H3('Preset Stations'),
        Div(*station_list),
        random_btn,
        Script(audio_js),
        style='max-width: 600px; margin: 0 auto; padding: 20px; font-family: Arial, sans-serif;'
    )

serve(host='0.0.0.0', port=8750)
