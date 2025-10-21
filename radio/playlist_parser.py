import requests
import re

def parse_playlist_url(url):
    """
    Parse .pls or .m3u playlist files and return direct stream URL.
    If URL is already a direct stream, return as-is.
    Prefers MP3 streams over AAC for better compatibility.
    """
    if not (url.endswith('.pls') or url.endswith('.m3u')):
        return url  # Already a direct stream URL

    try:
        response = requests.get(url, timeout=10)
        content = response.text

        if url.endswith('.pls'):
            # PLS format: File1=http://stream.url
            # Collect all File entries and prefer MP3
            mp3_urls = []
            all_urls = []

            for line in content.splitlines():
                match = re.search(r'File\d+=(.+)', line)
                if match:
                    stream_url = match.group(1).strip()
                    all_urls.append(stream_url)
                    if '-mp3' in stream_url:
                        mp3_urls.append(stream_url)

            # Prefer MP3 over AAC (AAC has compatibility issues)
            if mp3_urls:
                return mp3_urls[0]
            elif all_urls:
                return all_urls[0]

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
