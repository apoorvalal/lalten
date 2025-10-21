#!/usr/bin/env python3
"""
Test script to check which SomaFM stream variants work.
"""

import requests
import sys

def test_url(name, url):
    """Test if URL works and get first bytes."""
    try:
        response = requests.get(url, timeout=5, stream=True)
        content_type = response.headers.get('content-type', 'unknown')

        # Get first chunk
        chunk = next(response.iter_content(chunk_size=1024), None)

        if response.status_code == 200 and chunk:
            print(f"✓ {name:40} | {content_type:20} | {len(chunk):4} bytes")
            return True
        else:
            print(f"✗ {name:40} | Status: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ {name:40} | {str(e)[:50]}")
        return False

print("="*100)
print("TESTING SOMAFM STREAM VARIANTS")
print("="*100)
print()

stations_to_test = [
    'groovesalad',
    'dronezone',
    'deepspaceone',
    'secretagent',
    'lush'
]

ice_servers = ['ice2', 'ice4', 'ice6']
protocols = ['http', 'https']
formats = [
    ('256-mp3', 'MP3 256k'),
    ('128-mp3', 'MP3 128k'),
    ('128-aac', 'AAC 128k'),
    ('64-aacp', 'AAC+ 64k')
]

print(f"{'URL':60} | {'Type':20} | Status")
print("-" * 100)

results = {}

for station in stations_to_test:
    print(f"\n{station.upper()}")
    results[station] = []

    for protocol in protocols:
        for ice in ice_servers:
            for fmt_code, fmt_name in formats:
                url = f"{protocol}://{ice}.somafm.com/{station}-{fmt_code}"
                success = test_url(f"  {protocol.upper()} {ice} {fmt_name}", url)
                if success:
                    results[station].append((protocol, ice, fmt_code, fmt_name))

print("\n" + "="*100)
print("WORKING VARIANTS SUMMARY")
print("="*100)

for station, working in results.items():
    if working:
        print(f"\n{station}:")
        for protocol, ice, fmt_code, fmt_name in working:
            print(f"  ✓ {protocol}://{ice}.somafm.com/{station}-{fmt_code}")
    else:
        print(f"\n{station}: NO WORKING VARIANTS FOUND")
