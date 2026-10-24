import asyncio
import os

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():
    headers = {"Authorization": f"Bearer {os.environ['SWIGGY_TOKEN']}"}
    async with streamablehttp_client("https://mcp.swiggy.com/im", headers=headers) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            for t in (await s.list_tools()).tools:
                print("=" * 60)
                print("NAME:", t.name)
                print("DESC:", t.description)
                print("INPUT:", t.inputSchema)


if __name__ == "__main__":
    asyncio.run(main())
