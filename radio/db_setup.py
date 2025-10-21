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

        print("Loading stations...")
        for name, url in station_data.items():
            # Categorize by prefix
            if name.startswith('SOMA'):
                category = 'SomaFM'
            elif name in ['BLUE', 'CRYO', 'VOWI']:
                category = 'Bluemars'
            else:
                category = 'Other'

            # Store original URL (let proxy handle resolution)
            print(f"  {name}: {url}")

            stations.insert(
                name=name,
                url=url,
                stream_url=url,  # Store original, not resolved
                category=category,
                description=name,
                last_checked=None
            )

    return db
