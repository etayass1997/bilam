"""Serve the Bilam MCP tools and the legacy HTTP pages on one Render service."""

import os
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlparse

from a2wsgi import WSGIMiddleware
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from starlette.applications import Starlette
from starlette.routing import Mount

from app import PARASHOT, app as flask_app, search_sources, selected_parasha, text_stats


mcp = MCPServer(
    "bilam-torah",
    version="1.0.0",
    instructions=(
        "The corpus contains Torah verses and classical commentaries from Sefaria. "
        "Search before attributing a claim to a source; cite only returned source_label values. "
        "Use the counting tools for quantitative questions. All tools are read-only."
    ),
)
READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)


def _parasha_or_error(raw):
    if not raw:
        return None
    parasha = selected_parasha(raw)
    if not parasha:
        raise ValueError("פרשה לא מוכרת. קרא תחילה ל-list_parashot.")
    return parasha


@mcp.tool(title="רשימת פרשות", annotations=READ_ONLY)
def list_parashot() -> dict[str, Any]:
    """List the Torah portions available in Bilam's local source corpus."""
    return {"parashot": list(PARASHOT)}


@mcp.tool(title="חיפוש מקורות", annotations=READ_ONLY)
def search_torah_sources(query: str, parasha: str = "", limit: int = 6) -> dict[str, Any]:
    """Search Torah verses and classical commentaries; returns source text and exact citation labels. Use for factual claims about verses or commentators."""
    query = query.strip()
    if not query or len(query) > 500:
        raise ValueError("השאילתה צריכה להכיל 1 עד 500 תווים.")
    if not 1 <= limit <= 10:
        raise ValueError("limit חייב להיות בין 1 ל-10.")
    normalized = _parasha_or_error(parasha.strip())
    sources = search_sources(query, n=limit, parasha=normalized)
    return {"query": query, "parasha": normalized, "count": len(sources), "sources": sources}


@mcp.tool(title="ספירת מילה בתורה", annotations=READ_ONLY)
def count_word_in_torah(word: str, parasha: str = "", match_type: str = "exact_word") -> dict[str, Any]:
    """Count occurrences in Torah verse text only. exact_word matches a complete word; substring matches letters inside words and is not a linguistic root analysis. Returns exact totals and up to 25 example verses."""
    word = word.strip()
    if not word or len(word) > 50:
        raise ValueError("המילה צריכה להכיל 1 עד 50 תווים.")
    if match_type not in ("exact_word", "substring"):
        raise ValueError("match_type חייב להיות exact_word או substring.")
    normalized = _parasha_or_error(parasha.strip())
    return text_stats.count_word(word, match_type, parasha=normalized)


@mcp.tool(title="נתוני פרשה", annotations=READ_ONLY)
def get_parasha_stats(parasha: str) -> dict[str, Any]:
    """Return exact verse count, word count, and chapter numbers for one named Torah portion."""
    normalized = _parasha_or_error(parasha.strip())
    if not normalized:
        raise ValueError("נדרש שם פרשה. קרא תחילה ל-list_parashot.")
    return text_stats.get_parasha_stats(normalized)


def _transport_security():
    public_url = os.environ.get("PUBLIC_BASE_URL") or os.environ.get("RENDER_EXTERNAL_URL", "")
    hostname = urlparse(public_url).hostname
    hosts = ["localhost", "localhost:*", "127.0.0.1", "127.0.0.1:*"]
    if hostname:
        hosts.extend([hostname, f"{hostname}:*"])
    return TransportSecuritySettings(
        allowed_hosts=hosts,
        allowed_origins=[
            "http://localhost:*", "http://127.0.0.1:*",
            "https://chatgpt.com", "https://www.chatgpt.com",
        ],
    )


mcp_app = mcp.streamable_http_app(
    streamable_http_path="/",
    json_response=True,
    stateless_http=True,
    transport_security=_transport_security(),
)


@asynccontextmanager
async def lifespan(_app):
    async with mcp.session_manager.run():
        yield


app = Starlette(
    routes=[Mount("/mcp", app=mcp_app), Mount("/", app=WSGIMiddleware(flask_app))],
    lifespan=lifespan,
)
