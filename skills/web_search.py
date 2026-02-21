import requests
import re
from skills.manager import BaseSkill
from urllib.parse import quote_plus
import logging

class WebSearchSkill(BaseSkill):
    name = "WebSearch"
    description = "Searches the web for real-time information, news, and answers."

    def get_tools(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_web",
                    "description": "Searches the web using DuckDuckGo HTML and returns the top snippets.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query."
                            }
                        },
                        "required": ["query"]
                    }
                }
            }
        ]

    def search_web(self, query: str):
        try:
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            res = requests.get(url, headers=headers, timeout=10)
            res.raise_for_status()
            
            # Simple regex to extract snippets from DuckDuckGo HTML
            snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', res.text, re.IGNORECASE | re.DOTALL)
            
            if not snippets:
                return "No useful snippets found on the web for that query."
            
            clean_snippets = []
            for s in snippets[:5]:
                # Clean HTML tags
                clean_text = re.sub(r'<[^>]+>', '', s)
                clean_snippets.append(clean_text.strip())
                
            return "Web Search Results:\n- " + "\n- ".join(clean_snippets)
            
        except Exception as e:
            logging.error(f"Web search failed: {e}")
            return f"Error executing web search: {str(e)}"
