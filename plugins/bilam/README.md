# Bilam Plugin

This portable plugin contains a Hebrew Torah study skill. It uses the read-only Bilam MCP server for source retrieval and exact counts.

After deploying the repository's `backend/server.py` at a public HTTPS URL, run `python scripts/configure_plugin.py https://YOUR_SERVICE` from the repository root. This creates `mcp.json` and the skill's `agents/openai.yaml` with the deployed endpoint. Until that step, the package contains the skill but no live source connection.

See the repository [README](../../README.md) for deployment and ChatGPT connection steps.
