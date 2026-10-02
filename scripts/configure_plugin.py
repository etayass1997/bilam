"""Bind the portable Bilam plugin to its deployed HTTPS MCP endpoint."""

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse


PLUGIN_DIR = Path(__file__).resolve().parent.parent / "plugins" / "bilam"


def configure(base_url):
    parsed = urlparse(base_url.strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("נדרשת כתובת HTTPS ציבורית של השירות")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("יש למסור את כתובת בסיס השירות, ללא נתיב או פרמטרים")

    endpoint = f"https://{parsed.netloc.rstrip('/')}/mcp/"
    config = {
        "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
        "mcpServers": {"bilam": {"type": "streamable-http", "url": endpoint}},
    }
    (PLUGIN_DIR / "mcp.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    agent_dir = PLUGIN_DIR / "skills" / "torah-study" / "agents"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "openai.yaml").write_text(
        "dependencies:\n"
        "  tools:\n"
        "    - type: \"mcp\"\n"
        "      value: \"bilam\"\n"
        "      description: \"Read Torah verses, classical commentaries, and exact text counts\"\n"
        "      transport: \"streamable_http\"\n"
        f"      url: \"{endpoint}\"\n",
        encoding="utf-8",
    )
    return endpoint


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url", help="Deployed service URL, such as https://bilam.onrender.com")
    args = parser.parse_args()
    print(configure(args.base_url))
