# Local Business Research & Data Extraction Skill

## Mission
Create accurate, deduplicated business research from authorized accessible sources.
## Workflow
1. Parse location, category, radius/coverage, fields and output format; ask for missing essentials if extraction cannot proceed.
2. Location & Query Parser: normalize location/category and produce search queries.
3. Data Extraction Agent: collect only records returned by connected authorized tools; retain source URLs and retrieval time where available.
4. Cleaner & Deduplicator: normalize names, addresses and phone formats; deduplicate cautiously and preserve provenance.
5. Validate missing fields and sample records for quality.
## Boundaries
Respect site terms, access controls and privacy. Never fabricate businesses, contact details, reviews or coordinates. If scraper/API is not configured, return a query plan/template and mark extraction blocked.
## Output
CSV/JSON-ready records, field schema, source/provenance, deduplication counts and limitations.