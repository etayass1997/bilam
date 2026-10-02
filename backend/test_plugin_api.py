"""Integration checks for the deployed corpus and the four MCP tools."""

import asyncio
import unittest

from mcp import Client

import app
import server


class PluginApiTests(unittest.TestCase):
    def test_http_corpus_and_validation(self):
        client = app.app.test_client()
        self.assertGreater(client.get("/health").json["doc_count"], 180000)
        self.assertEqual(len(client.get("/api/parashot").json["parashot"]), 54)
        for path in ("/", "/manifest.json", "/service-worker.js"):
            response = client.get(path)
            try:
                self.assertEqual(response.status_code, 200)
                if path == "/":
                    self.assertIn("חיפוש מקורות".encode(), response.data)
            finally:
                response.close()
        self.assertEqual(client.post("/chat", json={}).status_code, 410)
        self.assertEqual(client.get("/api/search").status_code, 400)
        self.assertEqual(client.get("/api/parasha-stats?parasha=לא-קיימת").status_code, 400)

    def test_source_search_and_exact_count(self):
        client = app.app.test_client()
        search = client.get("/api/search", query_string={"query": "בלעם", "parasha": "בלק"}).json
        self.assertGreater(search["count"], 0)
        self.assertTrue(all(source["parasha"] == "פרשת בלק" for source in search["sources"]))
        self.assertTrue(all(source["source_label"] and source["text"] for source in search["sources"]))

        count = client.get("/api/count-word", query_string={"word": "בלעם", "parasha": "בלק"}).json
        self.assertGreater(count["total_occurrences"], 0)
        self.assertEqual(count["parasha"], "פרשת בלק")
        shown_total = sum(match["count"] for match in count["matches"])
        if count["matches_truncated"]:
            self.assertGreater(count["total_occurrences"], shown_total)
        else:
            self.assertEqual(count["total_occurrences"], shown_total)

    def test_mcp_tools(self):
        async def check():
            async with Client(server.mcp) as client:
                tools = await client.list_tools()
                names = {tool.name for tool in tools.tools}
                self.assertEqual(names, {
                    "list_parashot", "search_torah_sources", "count_word_in_torah", "get_parasha_stats"
                })
                result = await client.call_tool("get_parasha_stats", {"parasha": "בלק"})
                self.assertFalse(result.is_error)
                self.assertTrue(result.structured_content)

        asyncio.run(check())


if __name__ == "__main__":
    unittest.main()
