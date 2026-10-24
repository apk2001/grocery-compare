# Grocery Price Compare — backend

FastAPI backend for a grocery price-comparison MVP. It searches each store for
every item on a grocery list, asks an AgenticOrg agent to pick the best-matching
product per item, totals the prices from its own search data, and returns the
stores ranked cheapest-first.

```
POST /compare  { "location": {...}, "items": [...] }  ->  { "results": [ ...ranked stores... ] }
GET  /          ->  {"ok": true}   (health check)
```

## How it fits together

```
client ──(grocery list + location)──► /compare
                                         ├─ searches Zepto (Apify)  [+ Instamart (Swiggy MCP) if enabled]
                                         ├─ sends items + candidates to the AgenticOrg agent → best match per item
                                         ├─ keeps only picks whose sku_id exists in the search results
                                         └─ totals prices from its own data → ranks stores
```

The agent only **chooses** among products we pass it. It never searches, and
prices are always computed here, never taken from the agent.

## Environment variables

See `.env.example`. Required: `AGENTICORG_API_KEY`, `AGENT_ID`, `APIFY_TOKEN`.
`AGENTICORG_BASE_URL` defaults to the hackathon host. Instamart stays off until
`ENABLE_INSTAMART=true`, `SWIGGY_TOKEN` is set, and `SEARCH_TOOL` in
`adapters/instamart.py` is filled in (run `python tools/list_swiggy_tools.py`).

## Run locally (needs Python 3.11+ for the SDK-free deps; 3.9 works for the API too)

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
set -a; . ./.env; set +a
python main.py
# open http://localhost:8000/docs
```

## Deploy on Render

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Health check path: `/`
- Add the same env vars, plus `PYTHON_VERSION=3.11.9`.
