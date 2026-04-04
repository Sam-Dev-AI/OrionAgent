import urllib.request
import urllib.parse
import re
from enum import Enum
from orionagent.tools.decorator import tool


class WebAction(Enum):
    SEARCH = "search"
    FETCH = "fetch"


def cleanup_html(html: str) -> str:
    """Utility to strip script/style tags and return readable text to save tokens."""
    # Remove script and style elements
    html = re.sub(r'<(script|style|nav|footer|header).*?>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', html)
    # Manage whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:5000] # Cap at 5k chars for token safety


@tool
def web_browser(action: WebAction, query_or_url: str) -> str:
    """Searches the web via DuckDuckGo or fetches raw text content from a URL. 
    Use this to bridge training gaps with real-time world data.

    Args:
        action: The execution mode. 'search' for DuckDuckGo discovery, 'fetch' for direct URL reading.
        query_or_url: The search string (e.g., 'Latest Nvidia GPUs') or absolute URL (e.g., 'https://openai.com').
    """
    if isinstance(action, str):
        try:
            action = WebAction(action.lower())
        except ValueError:
            return f"Invalid action: {action}. Must be one of {[e.value for e in WebAction]}"

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        
        if action == WebAction.FETCH:
            req = urllib.request.Request(query_or_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                raw_html = response.read().decode('utf-8', errors='ignore')
                return cleanup_html(raw_html)

        elif action == WebAction.SEARCH:
            encoded_query = urllib.parse.quote(query_or_url)
            url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            req = urllib.request.Request(url, headers=headers)

            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8', errors='ignore')
                # Improved DDG parsing - looking for snippets
                snippets = re.findall(r'class="result__snippet".*?>(.*?)</a>', html, re.DOTALL)
                if not snippets:
                    # Fallback to general text extraction if class-based fails
                    return "No specific search snippets found. The site might be blocking automated requests. Try 'fetch' on a direct link."

                clean_snippets = []
                for s in snippets:
                    clean = re.sub(r'<[^>]+>', '', s).strip()
                    if clean:
                        clean_snippets.append(f"- {clean}")

                return "\n".join(clean_snippets[:5])

    except Exception as e:
        return f"Browser Error ({action.value}): {str(e)}"

    return "Unhandled Action."
