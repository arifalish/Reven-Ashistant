import re

with open('workers/maps_scraper_worker.py', 'r') as f:
    content = f.read()

new_scraper = """async def scrape_leads(city: str, niche: str) -> str:
    \"\"\"
    Placeholder for actual scraping logic via docker/GHA.
    For this robust OS, returns a highly realistic 8-column CSV layout.
    \"\"\"
    header = "name,address,phone,website,rating,reviews,lat/lng,emails\\n"
    r1 = f"{niche} Experts {city},\"123 Main St, {city}\",+1-555-0101,https://expert{niche.lower().replace(' ','')}.com,4.8,120,\"40.71,-74.00\",hello@expert{niche.lower().replace(' ','')}.com\\n"
    r2 = f"Top {niche} LLC,\"456 Broad St, {city}\",+1-555-0202,https://top{niche.lower().replace(' ','')}.com,4.5,85,\"40.72,-73.99\",contact@top{niche.lower().replace(' ','')}.com\\n"
    return header + r1 + r2"""

content = re.sub(r'async def scrape_leads.*?return header \+ r1 \+ r2', new_scraper, content, flags=re.DOTALL)

with open('workers/maps_scraper_worker.py', 'w') as f:
    f.write(content)
