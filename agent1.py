import asyncio
import os

import httpx

import cache
from adapters import zepto
from matcher import match
from models import MatchedItem, PlatformResult


def _key(platform, query, loc):
    return (platform, query.lower().strip(), round(loc.lat, 2), round(loc.lng, 2))


async def _cached_search(platform, search_fn, conn, query, loc):
    k = _key(platform, query, loc)
    hit = cache.get(k)
    if hit is not None:
        return hit
    try:
        res = await search_fn(conn, query, loc)
    except Exception as e:  # one bad item should not sink the whole store
        print(f"[{platform}] search failed for '{query}': {e}")
        res = []
    cache.put(k, res)
    return res


def _build_result(platform, items, cands, matches):
    out, missing, subtotal = [], [], 0.0
    for i in items:
        m = matches.get(i.id, {})
        # Only trust a pick whose sku_id actually exists in OUR search results.
        c = next((c for c in cands.get(i.id, []) if c.sku_id == m.get("sku_id")), None)
        if c is None:
            missing.append(i.id)
            out.append(MatchedItem(id=i.id, sku_id=None, name=None, unit_price=None, qty=i.qty, confidence=0))
            continue
        subtotal += c.price * i.qty
        out.append(
            MatchedItem(
                id=i.id,
                sku_id=c.sku_id,
                name=c.name,
                unit_price=c.price,
                qty=i.qty,
                confidence=float(m.get("confidence", 0)),
            )
        )
    return PlatformResult(platform=platform, items=out, subtotal=round(subtotal, 2), missing=missing)


async def _run(platform, search_fn, conn, items, loc):
    results = await asyncio.gather(*[_cached_search(platform, search_fn, conn, i.query, loc) for i in items])
    cands = {i.id: r for i, r in zip(items, results)}
    matches = await asyncio.to_thread(match, items, cands, platform)
    return _build_result(platform, items, cands, matches)


def _failed(platform, items, e):
    return PlatformResult(
        platform=platform, items=[], subtotal=0, missing=[i.id for i in items], error=str(e)
    )


async def run_zepto(items, loc):
    try:
        async with httpx.AsyncClient() as client:
            return await _run("zepto", zepto.search, client, items, loc)
    except Exception as e:
        return _failed("zepto", items, e)


async def run_instamart(items, loc):
    try:
        from adapters import instamart  # lazy: only needs the `mcp` package when enabled

        async with instamart.session() as s:
            return await _run("instamart", instamart.search, s, items, loc)
    except Exception as e:
        return _failed("instamart", items, e)


async def agent1(items, loc):
    jobs = [run_zepto(items, loc)]
    if os.environ.get("ENABLE_INSTAMART", "false").lower() == "true":
        jobs.append(run_instamart(items, loc))
    return list(await asyncio.gather(*jobs))
