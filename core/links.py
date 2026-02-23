"""
core/links.py — Link Understanding (Feature 7)

Dectects URLs in user messages, fetches their content, strips HTML,
and summarizes/truncates it to be injected as context for the LLM.
"""

import re
import logging
import requests
from html.parser import HTMLParser

class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.skip_tags = {'script', 'style', 'noscript', 'meta', 'head', 'link'}
        self.in_skip_tag = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self.in_skip_tag += 1

    def handle_endtag(self, tag):
        if tag in self.skip_tags:
            self.in_skip_tag = max(0, self.in_skip_tag - 1)

    def handle_data(self, data):
        if self.in_skip_tag == 0:
            text = data.strip()
            if text:
                self.text_parts.append(text)

    def get_text(self):
        return ' '.join(self.text_parts)

def fetch_url_text(url: str, max_chars: int = 8000) -> str:
    """Fetches a URL and extracts its text content."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    }
    try:
        res = requests.get(url, headers=headers, timeout=8)
        # Only process if 200 OK
        if res.status_code != 200:
            return f"Failed to fetch (HTTP {res.status_code})"
        
        content_type = res.headers.get("Content-Type", "").lower()
        if "text/html" in content_type:
            # Prevent massive HTML from blowing up the parser
            raw_html = res.text[:200000]
            parser = HTMLTextExtractor()
            parser.feed(raw_html)
            text = parser.get_text()
        elif "application/json" in content_type or "text/plain" in content_type:
            text = res.text[:200000]
        else:
            return f"Unsupported content type: {content_type.split(';')[0]}"

        # Clean multiple spaces and newlines
        text = re.sub(r'\s+', ' ', text).strip()
        
        if len(text) > max_chars:
            text = text[:max_chars] + "... [TRUNCATED]"
            
        return text if text else "No readable text found."
        
    except requests.Timeout:
        return "Fetch timed out."
    except Exception as e:
        logging.error(f"Error fetching URL {url}: {e}")
        return f"Fetch error: {e}"

def extract_and_fetch_links(message_text: str) -> str:
    """
    Finds URLs in the message, fetches them, and returns a formatted context block.
    If no URLs are found, returns an empty string.
    """
    # Regex to match http/https URLs
    url_pattern = re.compile(r'https?://[^\s<>"\']+|<https?://[^>]+>')
    urls = url_pattern.findall(message_text)
    
    # Clean up markdown/xml brackets if matched
    clean_urls = []
    for u in urls:
        u = u.strip('<>')
        if u not in clean_urls:
            clean_urls.append(u)
            
    if not clean_urls:
        return ""
        
    link_contexts = []
    for url in clean_urls[:3]:  # Limit to 3 URLs per message to avoid massive context
        logging.info(f"Link Understanding: Fetching {url}")
        content = fetch_url_text(url)
        link_contexts.append(f"[LINK CONTENT: {url}]\n{content}\n[/LINK CONTENT]")
        
    if link_contexts:
        return "\n\n" + "\n\n".join(link_contexts)
    return ""
