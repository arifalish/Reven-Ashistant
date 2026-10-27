import asyncio
import os
import aiohttp


class MapsScraperWorker:
    """Adapter for a separately deployed gosom/google-maps-scraper service."""

    def __init__(self, endpoint_url: str | None = None):
        self.endpoint_url = (endpoint_url or os.getenv("GOOGLE_MAPS_SCRAPER_URL", "")).rstrip("/")

    async def scrape_leads(self, city: str, niche: str) -> str:
        """Submit a real scraper job and return its CSV, or an explicit integration error."""
        if not self.endpoint_url:
            return "ERROR: GOOGLE_MAPS_SCRAPER_URL is not configured; no leads were scraped."

        payload = {
            "queries": [f"{niche} in {city}"],
            "depth": 5,
            "email": True,
            "max_time": 300,
        }
        timeout = aiohttp.ClientTimeout(total=330)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.post(self.endpoint_url, json=payload) as response:
                    if response.status not in (200, 201, 202):
                        body = (await response.text())[:500]
                        return f"ERROR: scraper service returned HTTP {response.status}: {body}"
                    data = await response.json()
                    job_id = data.get("job_id") or data.get("id")
                    if not job_id:
                        # Some compatible services return CSV synchronously.
                        if "csv" in data and isinstance(data["csv"], str):
                            return data["csv"]
                        return "ERROR: scraper service did not return a job_id or CSV result."

                for _ in range(60):
                    await asyncio.sleep(5)
                    async with session.get(f"{self.endpoint_url}/{job_id}") as status_response:
                        if status_response.status != 200:
                            continue
                        status_data = await status_response.json()
                        status = str(status_data.get("status", "")).lower()
                        if status in {"failed", "error", "cancelled"}:
                            return f"ERROR: scraper job {job_id} ended with status {status}."
                        if status in {"completed", "complete", "success", "succeeded"}:
                            async with session.get(f"{self.endpoint_url}/{job_id}/results?format=csv") as result_response:
                                if result_response.status == 200:
                                    return await result_response.text()
                                if isinstance(status_data.get("csv"), str):
                                    return status_data["csv"]
                                return f"ERROR: scraper job completed but result download returned HTTP {result_response.status}."
                return f"ERROR: scraper job {job_id} did not finish within the polling window."
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
                return f"ERROR: could not reach scraper service: {exc}"


scraper_worker = MapsScraperWorker()
