# homelab-asset-db-mcp

> Query a Markdown-based homelab asset database via Model Context Protocol.

A tiny [FastMCP](https://github.com/jlowin/fastmcp) stdio server that turns a
plain-Markdown inventory of your homelab (servers, LXC containers, Raspberry
Pis, smart-home gadgets, …) into structured MCP tools. An LLM connected via
MCP can then answer "where does `pve01` run", "which IP has the printer" or
"what's on the smart-home VLAN" directly — no reading and grepping the
Markdown file on every query.

Read-only, no hosting, no auth, no API credits. The data lives in a file you
own; this repo only carries the parser + a fictional sample.

## Why

Most homelab inventories live as a Markdown table in someone's notes. That's
great for humans and terrible for an agent, which has to fetch the whole file
and pattern-match every time. This server parses the tables once per call and
exposes four precise lookups instead.

Sibling to [`iobroker-mcp`](https://github.com/McCavity/iobroker-mcp),
[`paperless-bulk-mcp`](https://github.com/McCavity/paperless-bulk-mcp) and
[`nanobanana-render-mcp`](https://github.com/McCavity/nanobanana-render-mcp) —
same FastMCP scaffolding, different domain.

## Tools

| Tool | Argument | Purpose |
|---|---|---|
| `find_device(query)` | free-text string | full-text search across all fields |
| `get_device(name_or_hostname)` | exact name/hostname | a single device |
| `list_devices_by_vlan(vlan)` | VLAN name (substring) | all devices on a VLAN |
| `list_devices_by_category(cat)` | Server/LXC/RasPi/Office/SmartHome/Entertainment/Network/Unknown | all devices in a section |

All tools return JSON. Fields with no value are omitted from the response.

## Setup

```bash
git clone https://github.com/McCavity/homelab-asset-db-mcp.git
cd homelab-asset-db-mcp
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Out of the box the server reads the bundled `asset-db.sample.md` (fictional
data), so it runs immediately.

## Configuration

Point the server at your own database with the `ASSET_DB_PATH` environment
variable. Your real file stays outside this repo (it's gitignored):

```bash
export ASSET_DB_PATH=~/notes/homelab/asset-db.md
```

`~` is expanded. If `ASSET_DB_PATH` is unset, the bundled sample is used. A
`.env` file next to `server.py` is also read (see `.env.example`); values
already in the environment win, so an MCP host's `env` config takes precedence.

### Register with Claude Code

```bash
claude mcp add --transport stdio --scope user homelab-asset-db \
  --env ASSET_DB_PATH=/absolute/path/to/your/asset-db.md \
  -- /absolute/path/to/homelab-asset-db-mcp/venv/bin/python \
     /absolute/path/to/homelab-asset-db-mcp/server.py
```

Then `/mcp` lists the server and the four tools become callable in any session.

## Data format

The database is Markdown. Each `##` heading starts a section; the first table
row after it is the header, the rest are devices. Section headings are mapped
to categories in `CATEGORY_MAP` in `server.py` — headings not listed there
(e.g. a "Naming Scheme" table) are treated as documentation and skipped.
Columns may differ per section; each device keeps whatever columns its table
defines. Both English and German section headings are recognised. See
[`asset-db.sample.md`](asset-db.sample.md) for the full shape.

The file is re-parsed on every tool call — no caching, no restart when it
changes.

## Testing

```bash
python -m unittest discover -s tests -v
```

Covers the bundled English sample and a German fixture (so a change that
breaks real-world German-headed databases fails the suite).

## Known limits

- **No resources** (`@mcp.resource`) — devices without a hostname would have
  no stable URI. Could be added later with a slug generator.
- **No caching** — the file is re-parsed per call. Fine for a few hundred
  rows; cache + mtime-invalidate for larger inventories.
- **Read-only by design** — no write tools.

## License

[MIT](LICENSE) © 2026 Henning Halfpap
