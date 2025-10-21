#!/usr/bin/env python3
from fasthtml.common import *
import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

app, rt = fast_app()

def scrape_links(url, pat=None):
    """
    Scrapes all links on page, optionally accepts regex pattern.
    Uses requests and BeautifulSoup.
    Returns tuple: (success, result)
    - If success: (True, list_of_links)
    - If error: (False, error_message)
    """
    try:
        # Fetch the content of the URL
        response = requests.get(url, timeout=10)
        # Raise an exception for bad status codes (4xx or 5xx)
        response.raise_for_status()

        # Parse the HTML content using BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find all anchor tags with an href attribute
        all_links = soup.find_all('a', href=True)

        absolute_links = []
        for link in all_links:
            # Convert relative URLs to absolute URLs
            absolute_link = urljoin(url, link['href'])
            absolute_links.append(absolute_link)

        if pat:
            # Filter links based on the provided pattern
            try:
                filtered_links = [link for link in absolute_links if re.search(pat, link)]
                return (True, filtered_links)
            except re.error as e:
                return (False, f"Invalid regex pattern: {str(e)}")

        return (True, absolute_links)

    except requests.exceptions.Timeout:
        return (False, "Request timed out. The server took too long to respond.")
    except requests.exceptions.ConnectionError:
        return (False, "Connection error. Could not reach the URL.")
    except requests.exceptions.HTTPError as e:
        return (False, f"HTTP error: {e.response.status_code} - {e.response.reason}")
    except requests.exceptions.RequestException as e:
        return (False, f"Error during request: {str(e)}")
    except Exception as e:
        return (False, f"Unexpected error: {str(e)}")


# JavaScript for copy functionality
copy_js = """
function copyToClipboard() {
    const textarea = document.getElementById('resultsBox');
    textarea.select();
    document.execCommand('copy');

    // Visual feedback
    const btn = document.getElementById('copyBtn');
    const originalText = btn.textContent;
    btn.textContent = '✓ Copied!';
    btn.style.backgroundColor = '#28a745';

    setTimeout(() => {
        btn.textContent = originalText;
        btn.style.backgroundColor = '#007bff';
    }, 2000);
}

function showLoading() {
    const resultsDiv = document.getElementById('resultsSection');
    if (resultsDiv) {
        resultsDiv.style.opacity = '0.6';
    }
}
"""

@rt('/')
def get():
    """Main page with input form"""

    # Example patterns section
    examples = Div(
        H3('Example Regex Patterns:', style='margin-top: 20px; color: #555;'),
        Ul(
            Li(Code('.*\\.pdf$'), ' - All PDF files'),
            Li(Code('.*\\.(jpg|png|gif|webp)$'), ' - All images'),
            Li(Code('.*\\.(pdf|doc|docx|ppt|pptx)$'), ' - All documents'),
            Li(Code('https://example\\.com/.*'), ' - Links from specific domain'),
            Li('Leave blank to extract all links'),
            style='background-color: #f9f9f9; padding: 15px; border-radius: 5px; line-height: 1.8;'
        ),
        style='margin-top: 20px;'
    )

    # Input form
    form = Form(
        Div(
            Label('Target URL:', style='font-weight: bold; display: block; margin-bottom: 5px;'),
            Input(
                type='text',
                name='url',
                placeholder='https://example.com/page',
                required=True,
                style='width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; font-size: 1em;'
            ),
            style='margin-bottom: 15px;'
        ),
        Div(
            Label('Regex Pattern (optional):', style='font-weight: bold; display: block; margin-bottom: 5px;'),
            Input(
                type='text',
                name='pattern',
                placeholder='.*\\.pdf$ (leave blank for all links)',
                style='width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; font-size: 1em;'
            ),
            style='margin-bottom: 15px;'
        ),
        Button(
            '🔍 Extract Links',
            type='submit',
            onclick='showLoading()',
            style='width: 100%; padding: 12px; background-color: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 1.1em; font-weight: bold;'
        ),
        method='post',
        action='/linkpull/extract'
    )

    return Titled('LinkPull - URL Extractor',
        Div(
            H1('🔗 LinkPull', style='color: #007bff; margin-bottom: 10px;'),
            P('Extract and filter URLs from any webpage', style='color: #666; font-size: 1.1em;'),
            Hr(style='margin: 20px 0;'),
            form,
            examples,
            style='max-width: 800px; margin: 0 auto; padding: 20px; font-family: Arial, sans-serif;'
        ),
        Script(copy_js)
    )


@rt('/extract')
def post(url: str, pattern: str = None):
    """Process the URL and extract links"""

    # Clean up inputs
    url = url.strip()
    pattern = pattern.strip() if pattern else None

    # Validate URL format
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    # Extract links
    success, result = scrape_links(url, pattern)

    if success:
        links = result
        links_text = '\n'.join(links)
        count = len(links)

        # Results section
        results_section = Div(
            H3(f'✓ Found {count} matching link{"s" if count != 1 else ""}',
               style='color: #28a745; margin-bottom: 15px;'),
            Div(
                Textarea(
                    links_text,
                    id='resultsBox',
                    readonly=True,
                    rows='20',
                    style='width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; font-family: monospace; font-size: 0.9em; resize: vertical;'
                ),
                Button(
                    '📋 Copy All Links',
                    id='copyBtn',
                    onclick='copyToClipboard()',
                    style='margin-top: 10px; padding: 10px 20px; background-color: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 1em;'
                ) if count > 0 else None,
                style='margin-top: 10px;'
            ),
            id='resultsSection',
            style='margin-top: 30px; padding: 20px; background-color: #f9f9f9; border-radius: 5px; border: 1px solid #ddd;'
        )

        status_message = results_section
    else:
        # Error message
        error_msg = result
        status_message = Div(
            H3('✗ Error', style='color: #dc3545; margin-bottom: 10px;'),
            P(error_msg, style='color: #666;'),
            style='margin-top: 30px; padding: 20px; background-color: #fff3cd; border-radius: 5px; border: 1px solid #ffc107;'
        )

    # Show form again with results
    form = Form(
        Div(
            Label('Target URL:', style='font-weight: bold; display: block; margin-bottom: 5px;'),
            Input(
                type='text',
                name='url',
                value=url,
                required=True,
                style='width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; font-size: 1em;'
            ),
            style='margin-bottom: 15px;'
        ),
        Div(
            Label('Regex Pattern (optional):', style='font-weight: bold; display: block; margin-bottom: 5px;'),
            Input(
                type='text',
                name='pattern',
                value=pattern if pattern else '',
                style='width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; font-size: 1em;'
            ),
            style='margin-bottom: 15px;'
        ),
        Button(
            '🔍 Extract Links',
            type='submit',
            onclick='showLoading()',
            style='width: 100%; padding: 12px; background-color: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 1.1em; font-weight: bold;'
        ),
        method='post',
        action='/linkpull/extract'
    )

    return Titled('LinkPull - Results',
        Div(
            H1('🔗 LinkPull', style='color: #007bff; margin-bottom: 10px;'),
            P('Extract and filter URLs from any webpage', style='color: #666; font-size: 1.1em;'),
            Hr(style='margin: 20px 0;'),
            form,
            status_message,
            Div(
                A('← Start New Search', href='/linkpull',
                  style='display: inline-block; margin-top: 20px; padding: 10px 20px; background-color: #6c757d; color: white; text-decoration: none; border-radius: 5px;'),
                style='text-align: center;'
            ),
            style='max-width: 800px; margin: 0 auto; padding: 20px; font-family: Arial, sans-serif;'
        ),
        Script(copy_js)
    )


if __name__ == '__main__':
    serve(host='0.0.0.0', port=8743)
