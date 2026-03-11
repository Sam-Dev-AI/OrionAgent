import urllib.request
import urllib.parse
from enum import Enum
from orionagent.tools.decorator import tool


class WebAction(Enum):
    SEARCH = "search"
    FETCH = "fetch"


@tool
def web_browser(action: WebAction, query_or_url: str) -> str:
    """A browser simulator to search the public web or fetch raw page contents.

    Args:
        action (WebAction): The action to perform (search or fetch).
        query_or_url (str): The search query (if searching) or the full URL (if fetching).
    """
    if isinstance(action, str):
        try:
            action = WebAction(action.lower())
        except ValueError:
            return f"Invalid action: {action}. Must be one of {[e.value for e in WebAction]}"

    try:
        if action == WebAction.FETCH:
            req = urllib.request.Request(query_or_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                return response.read().decode('utf-8')

        elif action == WebAction.SEARCH:
            encoded_query = urllib.parse.quote(query_or_url)
            url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})

            with urllib.request.urlopen(req) as response:
                html = response.read().decode('utf-8')
                lines = [line.strip() for line in html.split('\n') if 'class="result__snippet"' in line]
                if not lines:
                    return "No text snippets found. Try using fetch on specific links."

                clean_lines = []
                for l in lines:
                    if '>' in l and '<' in l:
                        parts = l.split('<')
                        cleaned = "".join([p.split('>')[-1] for p in parts if '>' in p])
                        if cleaned:
                            clean_lines.append(cleaned)

                return "\n".join(clean_lines[:5])

    except Exception as e:
        return f"Browser Error ({action.value}): {str(e)}"

    return "Unhandled Action."
