import os

import httpx

from models import Candidate, Location

# Apify actor that scrapes Blinkit search results (same publisher/shape as Zepto).
ACTOR = "solidcode~blinkit-scraper"
ENDPOINT = f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items"
MAX_RESULTS = 6


async def search(client: httpx.AsyncClient, query: str, loc: Location) -> list[Candidate]:
    payload = {
        "searchTerms": [query],
        "startUrls": [],
        "city": loc.city or "",
        "latitude": str(loc.lat),
        "longitude": str(loc.lng),
        "maxResults": MAX_RESULTS,
    }
    r = await client.post(
        ENDPOINT,
        params={"token": os.environ["APIFY_TOKEN"]},
        json=payload,
        timeout=150,
    )
    r.raise_for_status()
    out: list[Candidate] = []
    for p in r.json()[:MAX_RESULTS]:
        if p.get("price") is None:
            continue
        out.append(
            Candidate(
                sku_id=str(p.get("productId") or p.get("url") or p.get("name")),
                name=p.get("name", ""),
                price=float(p["price"]),
                mrp=p.get("mrp"),
                pack_size=p.get("unit") or p.get("packSize"),
                in_stock=bool(p.get("inStock", True)),
            )
        )
    return out
