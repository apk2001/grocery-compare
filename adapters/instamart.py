import json
import os
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from models import Candidate, Location

URL = "https://mcp.swiggy.com/im"
SEARCH_TOOL = "TODO_search_tool_name"  # fill in after running tools/list_swiggy_tools.py
MAX_RESULTS = 6


@asynccontextmanager
async def session():
    headers = {"Authorization": f"Bearer {os.environ['SWIGGY_TOKEN']}"}
    async with streamablehttp_client(URL, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as s:
            await s.initialize()
            yield s


def _parse(result) -> list[dict]:
    for block in result.content:
        if getattr(block, "type", "") == "text":
            try:
                data = json.loads(block.text)
            except json.JSONDecodeError:
                continue
            return data if isinstance(data, list) else data.get("products", [])
    return []


async def search(s, query: str, loc: Location) -> list[Candidate]:
    result = await s.call_tool(SEARCH_TOOL, {"query": query})
    out: list[Candidate] = []
    for p in _parse(result)[:MAX_RESULTS]:
        out.append(
            Candidate(
                sku_id=str(p.get("id") or p.get("sku_id") or p.get("product_id")),
                name=p.get("name", ""),
                price=float(p.get("price") or p.get("offer_price") or 0),
                mrp=p.get("mrp"),
                pack_size=p.get("quantity") or p.get("pack_size"),
                in_stock=bool(p.get("in_stock", True)),
            )
        )
    return out
