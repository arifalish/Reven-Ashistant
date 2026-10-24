import httpx
import asyncio

class PublicWebReader:
    """
    Standard Public Web Documentation Fetcher.
    Uses httpx and Jina Reader to fetch public page text cleanly.
    Respects standard timeouts.
    """
    def __init__(self, use_jina: bool = True):
        self.use_jina = use_jina
        self.timeout = httpx.Timeout(15.0, read=30.0)

    async def fetch_public_page(self, url: str) -> str:
        target_url = f"https://r.jina.ai/{url}" if self.use_jina else url

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                # Basic public fetch without stealth or evasion
                response = await client.get(target_url)
                response.raise_for_status()
                return response.text
            except httpx.HTTPStatusError as exc:
                print(f"HTTP error fetching {url}: {exc.response.status_code}")
                return f"[WebReader] Error: HTTP {exc.response.status_code}"
            except Exception as e:
                print(f"Error fetching {url}: {e}")
                return f"[WebReader] Error: {str(e)}"

web_reader = PublicWebReader()
