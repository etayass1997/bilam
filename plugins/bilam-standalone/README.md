# Bilam standalone plugin

`../../dist/bilam-standalone.zip` is a shareable, skills-only plugin package. It
contains all 184,977 source records and a standard-library Python tool for
BM25 retrieval, exact verse counts, portion statistics, and basic DOCX export.
It has no MCP URL, server dependency, or model API key.

Rebuild after corpus changes:

```text
python scripts/build_standalone_plugin.py
```

The recipient needs a ChatGPT or Codex environment that can install plugins,
read packaged skill files, and execute Python scripts. Plugin installation and
public listing are subject to the recipient's product permissions and OpenAI's
plugin review. Code execution of bundled scripts has not been verified in every
ChatGPT client, so test the installed package on the target surface before
claiming the exact search and counts work there.

To distribute through the public plugin directory, upload the ZIP through the
OpenAI plugin portal and complete its identity verification and review flow:
https://developers.openai.com/plugins/deploy/submission

For local inspection, extract the ZIP and run:

```text
python skills/bilam-study/scripts/bilam_cli.py list
python skills/bilam-study/scripts/bilam_cli.py search "בלעם" --parasha "בלק"
python skills/bilam-study/scripts/bilam_cli.py count "ברכה" --parasha "בלק"
```
