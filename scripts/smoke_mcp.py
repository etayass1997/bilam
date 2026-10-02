"""Smoke-test a running Bilam MCP endpoint over HTTP."""

import argparse
import asyncio
import json
from urllib.request import urlopen

from mcp import Client


async def check(base_url):
    base_url = base_url.rstrip("/")
    with urlopen(f"{base_url}/health", timeout=15) as response:
        health = json.load(response)
    assert health["status"] == "ok" and health["doc_count"] > 0, health

    async with Client(f"{base_url}/mcp/") as client:
        listing = await client.list_tools()
        names = {tool.name for tool in listing.tools}
        expected = {"list_parashot", "search_torah_sources", "count_word_in_torah", "get_parasha_stats"}
        assert names == expected, names
        result = await client.call_tool("get_parasha_stats", {"parasha": "בלק"})
        assert not result.is_error, result
        assert result.structured_content["total_verses"] > 0, result
    print(f"MCP OK: {len(names)} tools, {health['doc_count']} source records")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url", nargs="?", default="http://127.0.0.1:5007")
    args = parser.parse_args()
    asyncio.run(check(args.base_url))
