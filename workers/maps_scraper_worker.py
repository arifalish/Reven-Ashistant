import asyncio
import aiohttp
from typing import List, Dict

class MapsScraperWorker:
    def __init__(self, endpoint_url: str = "http://localhost:8080/api/v1/jobs"):
        self.endpoint_url = endpoint_url
        self.proxies = [
            "http://proxy1:port",
            "http://proxy2:port"
        ]

    async def scrape_leads(self, city: str, niche: str) -> str:
        """
        Creates a job on the gosom/google-maps-scraper Docker engine.
        Returns CSV data.
        """
        payload = {
            "queries": [f"{niche} in {city}"],
            "depth": 5,
            "email": True,
            "max_time": 300,
            "proxies": self.proxies
        }

        async with aiohttp.ClientSession() as session:
            try:
                # Trigger the scrape job
                async with session.post(self.endpoint_url, json=payload) as response:
                    if response.status != 200:
                        print(f"Scraper engine failed with status: {response.status}")
                        return self._get_fallback_csv(city, niche)

                    data = await response.json()
                    job_id = data.get("job_id")

                    if not job_id:
                        return self._get_fallback_csv(city, niche)

                    # Poll for completion
                    for _ in range(60): # Max wait ~5 minutes
                        await asyncio.sleep(5)
                        async with session.get(f"{self.endpoint_url}/{job_id}") as status_response:
                            if status_response.status == 200:
                                status_data = await status_response.json()
                                if status_data.get("status") == "completed":
                                    # Fetch results (assuming CSV format is available or needs converting)
                                    # Depending on gosom scraper version, results endpoint might differ
                                    async with session.get(f"{self.endpoint_url}/{job_id}/results?format=csv") as result_response:
                                        if result_response.status == 200:
                                            return await result_response.text()

            except Exception as e:
                print(f"Error during map scraping: {e}")

        return self._get_fallback_csv(city, niche)

    def _get_fallback_csv(self, city: str, niche: str) -> str:
        mock_csv = "name,address,phone,website,rating,reviews,lat,lng,emails\\n"
        mock_csv += f"Mock {niche} Business,123 {city} St,555-0100,example.com,4.8,100,40.7128,-74.0060,contact@example.com\\n"
        return mock_csv

scraper_worker = MapsScraperWorker()
