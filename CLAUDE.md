# homelab-asset-db-mcp — Conventions for AI agents

> Last update: 2026-07-17

This file orients AI coding agents (Claude Code, Codex, etc.) working on this
repository. Humans should read [README.md](README.md) first.

## What this project is

A Model Context Protocol server that exposes a Markdown-based homelab asset
database as four read-only lookup tools. Sibling to `iobroker-mcp`,
`paperless-bulk-mcp` and `nanobanana-render-mcp` — same FastMCP scaffolding,
different domain. Transport: stdio. Framework: FastMCP.

## Key design choices

- **Single `server.py`, no package split.** Four tools, ~300 lines. Split
  only if it grows well past that.
- **Data lives in a file the user owns, not in this repo.** The real
  `asset-db.md` is gitignored; only the fictional `asset-db.sample.md` is
  committed. This keeps private homelab data (IPs, MACs, hostnames) out of a
  public repository — never add a real inventory here.
- **Path resolution:** `ASSET_DB_PATH` env wins, else the bundled sample. A
  non-overriding `.env` loader (next to `server.py`) is a manual-run
  convenience; an MCP host's `env` config always takes precedence.
- **Parse on every call, no cache.** The file is small; correctness beats a
  stale cache. Add mtime-invalidation only if inventories get large.
- **Bilingual section headings.** `CATEGORY_MAP` recognises both English and
  German headings so the same parser serves an English sample and a German
  production DB. Add new headings there, not by special-casing the parser.

## Parser contract

- `## Heading` starts a section; the first `|...|` row after it is the header,
  subsequent rows are devices.
- A section whose heading is **not** in `CATEGORY_MAP` is skipped (treated as
  prose/documentation).
- Ragged rows (cell count ≠ header count) are skipped, not fatal.
- A blank line resets table state, so two tables separated by prose relearn
  their headers.
- `_normalize_value` maps empty cells and dashes (`—`, `-`, `–`) to `None`;
  `_record_summary` drops `None` fields from tool output.

## Coding conventions

- Python 3.11+ (developed on Homebrew Python 3.14).
- Type hints everywhere (`from __future__ import annotations` at top).
- Tool docstrings are the user-facing contract — write them as if the next
  caller is an LLM with nothing else to go on.

## Testing

`python -m unittest discover -s tests -v`. The suite runs without pytest.
Every parser or CATEGORY_MAP change must keep both the English-sample and the
German-fixture tests green.
