# LinkPull Web Application Specification

## Overview
A simple web application that scrapes URLs from a target webpage based on regex patterns and displays matching links in a copy-pasteable plaintext format. This webapp integrates with existing `linkPull` (link extraction only) and `getter2` (download functionality) scripts.

## Functional Requirements

### Core Features
1. **URL Input**: Accept a static URL from user
2. **Regex Pattern Input**: Accept a regex pattern to filter links (optional, defaults to all links)
3. **Link Extraction**: Scrape all links from the target page and apply regex filter
4. **Display Results**: Show full absolute URLs in a plaintext box
5. **Copy-Paste Support**: Enable easy copying of all links or individual links

### User Interface Components
1. **Input Form**
   - URL input field (required)
   - Regex pattern input field (optional, with helpful examples)
   - Submit button

2. **Results Display**
   - Large textarea with all matching URLs (one per line)
   - Copy-all button for one-click clipboard copy
   - Link count display
   - Status messages (loading, error, success)

3. **Features List**
   - **linkPull mode**: Display only (no downloading)
   - **getter2 mode**: Integration hint - copy links for use with getter2 script

### Example Use Cases
- Extract all PDF links: `.*\.pdf$`
- Extract all images: `.*\.(jpg|png|gif|webp)$`
- Extract all documents: `.*\.(pdf|doc|docx|ppt|pptx)$`
- Extract all links from specific domain: `https://example\.com/.*`
- Extract all links (no pattern): leave blank or use `.*`

## Technical Architecture

### Backend
- **Framework**: FastHTML (matching existing radio app architecture)
- **Port**: 8743 (next available port after menu:8742)
- **Dependencies**:
  - `fasthtml`
  - `requests` (for HTTP requests)
  - `beautifulsoup4` (for HTML parsing)
  - `re` (standard library, for regex)

### Core Functions (from existing scripts)
Reuse logic from `getter2` and `linkPull`:
```python
def scrape_links(url, pat=None):
    """
    Scrapes all links from URL, optionally filters by regex pattern.
    Returns list of absolute URLs.
    Uses requests + BeautifulSoup (from getter2)
    """
    - Fetch page with requests
    - Parse HTML with BeautifulSoup
    - Extract all <a href> tags
    - Convert relative URLs to absolute
    - Filter by regex pattern if provided
    - Return list of matching URLs
```

### Frontend
- **Style**: Simple, clean interface matching radio app aesthetic
- **Components**:
  - Input form at top
  - Results textarea (read-only, full-width)
  - Copy button with visual feedback
  - Helpful hints/examples for regex patterns

### URL Structure
- Main page: `/linkpull` or `/linkpull/`
- Form submission: POST to `/linkpull/extract`
- Nginx proxy: `/linkpull/` → `http://127.0.0.1:8743/`

## Implementation Plan

### Phase 1: Core Backend
1. Create `main.py` with FastHTML app setup
2. Implement `scrape_links()` function (adapted from existing scripts)
3. Create route for main page (GET /)
4. Create route for extraction (POST /extract)

### Phase 2: Frontend
1. Design input form with URL and regex fields
2. Create results display area
3. Add example patterns and help text
4. Implement copy-to-clipboard functionality
5. Add loading states and error handling

### Phase 3: Integration
1. Configure nginx to proxy `/linkpull/` to port 8743
2. Test with various URLs and patterns
3. Document usage in README

### Phase 4: Enhancement (Optional)
1. Save recent queries (local storage or simple DB)
2. Pre-fill common patterns dropdown
3. Download all button (integration with getter2 logic)
4. URL validation and preview

## File Structure
```
linkpull/
├── getter2              # Existing: download script
├── linkPull             # Existing: CLI link extraction script
├── spec.md              # This file
├── main.py              # New: FastHTML web application
├── requirements.txt     # New: Python dependencies
└── README.md            # New: Usage documentation
```

## Dependencies
```
fasthtml
requests
beautifulsoup4
```

## Nginx Configuration Addition
```nginx
location /linkpull/ {
    proxy_pass http://127.0.0.1:8743/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}

location = /linkpull {
    proxy_pass http://127.0.0.1:8743/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

## User Flow
1. User navigates to `https://lalten.org/linkpull`
2. User enters target URL (e.g., `https://example.com/documents/`)
3. User enters regex pattern (e.g., `.*\.pdf$`) or leaves blank for all links
4. User clicks "Extract Links"
5. Application scrapes page and filters links
6. Results displayed in textarea (one URL per line)
7. User clicks "Copy All Links" to copy to clipboard
8. User can paste into getter2 or use as needed

## Error Handling
- Invalid URL format → Display error message
- Network timeout → Display timeout message with retry option
- No links found → Display "No matching links found"
- Invalid regex → Display regex error with helpful hint
- HTTP errors (403, 404, 500) → Display appropriate error message

## Security Considerations
- No authentication required (internal tool)
- Rate limiting to prevent abuse (optional)
- URL validation to prevent SSRF (validate http/https schemes)
- Regex timeout to prevent ReDoS attacks
- No persistent storage of URLs or results (privacy)

## Success Metrics
- Successfully extracts links from various webpage types
- Regex filtering works correctly
- Copy-paste functionality works in all major browsers
- Page loads in < 2 seconds
- Link extraction completes in < 10 seconds for typical pages
