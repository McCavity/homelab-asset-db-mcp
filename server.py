"""
homelab-asset-db-mcp
====================

FastMCP server that exposes a Markdown-based homelab asset database as MCP
tools, so an LLM connected via MCP can answer questions like "where does
pve01 run", "which IP has the printer" or "what's on the smart-home VLAN"
without reading and grepping the Markdown file on every query.

Tools:
  - find_device(query)              full-text search across all fields
  - get_device(name_or_hostname)    exact lookup
  - list_devices_by_vlan(vlan)      filtered by VLAN
  - list_devices_by_category(cat)   filtered by section (Server/LXC/RasPi/...)

Data source: Markdown tables (section -> header -> data rows), parsed by a
small state machine. Columns vary per section; each stored record keeps all
fields found in its table plus `_category` (short name) and `_section`
(original heading).

The database file is read fresh on every tool call — no caching, no restart
needed when the file changes. Path resolution:

  1. `ASSET_DB_PATH` environment variable, if set (expanduser applied), else
  2. the bundled `asset-db.sample.md` next to this file.

Point `ASSET_DB_PATH` at your own asset DB to keep private data out of this
repository; the bundled sample keeps the server runnable out of the box.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def _load_dotenv() -> None:
    """Load KEY=VALUE lines from a `.env` next to this file, if present.

    Dependency-free and non-overriding: variables already in the environment
    (e.g. passed by the MCP host via its `env` config) take precedence, so the
    `.env` file is only a convenience for manual runs.
    """
    env_file = Path(__file__).resolve().parent / ".env"
    if not env_file.exists():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()

# Bundled fictional sample DB, next to this file. Runnable out of the box and
# used as the documented example. Real deployments override via ASSET_DB_PATH.
_DEFAULT_DB_PATH = Path(__file__).resolve().parent / "asset-db.sample.md"

# Env var wins; fall back to the bundled sample. `expanduser` so `~/...` works.
ASSET_DB_PATH = Path(os.environ.get("ASSET_DB_PATH", _DEFAULT_DB_PATH)).expanduser()

# Mapping from section headings (as written in the Markdown file) to compact
# category names for the API. Sections not listed here are treated as prose
# (e.g. a naming-scheme table) and skipped, not as devices.
CATEGORY_MAP: dict[str, str] = {
    "Server & Infrastruktur": "Server",
    "Server & Infrastructure": "Server",
    "LXC-Container (auf Proxmox)": "LXC",
    "LXC Containers": "LXC",
    "Raspberry Pis": "RasPi",
    "Netzwerk-Infrastruktur (UniFi)": "Network",  # pointer section only
    "Network Infrastructure": "Network",
    "Büro / Arbeitsplatz": "Büro",
    "Office / Workspace": "Office",
    "Smart Home / IoT": "SmartHome",
    "Lokale Dienste (macOS)": "LocalService",
    "Local Services (macOS)": "LocalService",
    "Unterhaltung": "Entertainment",
    "Entertainment": "Entertainment",
    "Klärungsbedarf": "Unknown",
    "Needs Clarification": "Unknown",
}


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

_SECTION_RE = re.compile(r"^##\s+(?P<title>.+?)\s*$")
_TABLE_SEP_RE = re.compile(r"^\s*\|\s*-{3,}.*\|\s*$")


def _split_row(line: str) -> list[str]:
    """Split a Markdown table row into cells.

    Strips leading/trailing pipes and trims each cell.
    """
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [cell.strip() for cell in line.split("|")]


def _normalize_value(value: str) -> str | None:
    """Em-dash ('—') and empty strings -> None."""
    v = value.strip()
    if v in ("", "—", "-", "–"):
        return None
    return v


def parse_asset_db(path: Path = ASSET_DB_PATH) -> list[dict]:
    """Parse the asset DB into a list of dicts.

    Each record holds the columns of its table plus `_category` (short name
    from CATEGORY_MAP) and `_section` (original heading).
    """
    devices: list[dict] = []
    current_section: str | None = None
    current_headers: list[str] | None = None

    if not path.exists():
        return devices

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()

        # Section heading
        m_sec = _SECTION_RE.match(line)
        if m_sec:
            current_section = m_sec.group("title").strip()
            current_headers = None  # next table brings new headers
            continue

        # Skip the table separator row (|---|---|)
        if _TABLE_SEP_RE.match(line):
            continue

        # Table row?
        if line.startswith("|"):
            cells = _split_row(line)
            if current_headers is None:
                # first row of a new table = header
                current_headers = cells
                continue

            # Data row
            if len(cells) != len(current_headers):
                # ragged — skip instead of crashing
                continue

            # Only process sections defined in CATEGORY_MAP. Other tables
            # (e.g. "Naming Scheme") are documentation, not devices.
            if current_section not in CATEGORY_MAP:
                continue

            record: dict = {
                "_section": current_section,
                "_category": CATEGORY_MAP[current_section],
            }
            for header, value in zip(current_headers, cells):
                record[header] = _normalize_value(value)
            # Skip sections without usable data (e.g. a pointer to another file)
            if not any(record[h] for h in current_headers):
                continue
            devices.append(record)
            continue

        # Anything else (paragraphs, blank lines, code fences, ...) resets the
        # table state, so two tables separated by prose are relearned cleanly.
        if not line:
            current_headers = None

    return devices


# ---------------------------------------------------------------------------
# Helpers for the tool implementations
# ---------------------------------------------------------------------------

# Fields considered by full-text search / lookup (string fields across sections).
_SEARCHABLE_FIELDS: tuple[str, ...] = (
    "Name", "Hostname", "IP", "VLAN", "Typ", "Type", "Notizen", "Notes",
    "Dienst", "Service", "Funktion", "Function", "Hardware", "Dienste / URL",
    "Services / URL", "Raum", "Room", "MAC", "Problem", "Gerät", "Device",
)

# Fields treated as a "name" for get_device (match order: Hostname, Name, Device).
_NAME_FIELDS: tuple[str, ...] = ("Hostname", "Name", "Gerät", "Device")


def _matches(record: dict, query: str) -> bool:
    """True if `query` (case-insensitive) occurs in any searchable field."""
    q = query.lower()
    for field in _SEARCHABLE_FIELDS:
        value = record.get(field)
        if value and q in value.lower():
            return True
    return False


def _exact_name_match(record: dict, name: str) -> bool:
    """True if `name` matches one of the name fields exactly (case-insensitive)."""
    n = name.strip().lower()
    for field in _NAME_FIELDS:
        value = record.get(field)
        if value and value.strip().lower() == n:
            return True
    return False


def _record_summary(record: dict) -> dict:
    """Stripped representation for JSON output (drop None fields)."""
    return {k: v for k, v in record.items() if v is not None}


# ---------------------------------------------------------------------------
# MCP server + tools
# ---------------------------------------------------------------------------

mcp = FastMCP("homelab-asset-db")


@mcp.tool()
def find_device(query: str) -> str:
    """Full-text search across every device in the asset DB.

    Searches Name, Hostname, IP, VLAN, Type, Notes, Service, Function,
    Hardware, Room, MAC and the Problem field (case-insensitive substring).

    Args:
        query: search term (e.g. "grafana", "192.0.2", "Raspberry", "Office")

    Returns:
        JSON string with the list of hits. Empty list if nothing matches.
    """
    if not query.strip():
        return json.dumps({"error": "Empty search query."})

    devices = parse_asset_db()
    hits = [_record_summary(d) for d in devices if _matches(d, query)]

    return json.dumps({
        "query": query,
        "count": len(hits),
        "results": hits,
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def get_device(name_or_hostname: str) -> str:
    """Exact lookup of a device by hostname, name or device label.

    Match order: hostname first, then name, then the device column (for the
    "needs clarification" section). Case-insensitive but an exact match
    (no substring).

    Args:
        name_or_hostname: e.g. "pve01" or "Office NAS" or "BluRay Player"

    Returns:
        JSON string with device details. If not found: an error field.
    """
    if not name_or_hostname.strip():
        return json.dumps({"error": "Empty lookup key."})

    devices = parse_asset_db()
    for d in devices:
        if _exact_name_match(d, name_or_hostname):
            return json.dumps(_record_summary(d), ensure_ascii=False, indent=2)

    return json.dumps({
        "error": f"No device with hostname/name/device '{name_or_hostname}' found.",
        "hint": "Try find_device() for a substring search.",
    }, ensure_ascii=False)


@mcp.tool()
def list_devices_by_vlan(vlan: str) -> str:
    """All devices on a given VLAN.

    VLAN match is a case-insensitive substring (e.g. "smart home" matches
    "Smart Home").

    Args:
        vlan: VLAN name from the asset DB (e.g. "Smart Home", "HomeLab",
              "Legacy LAN", "Camera", "Entertainment", "Guest" — not exhaustive).

    Returns:
        JSON with the list of devices on the VLAN.
    """
    if not vlan.strip():
        return json.dumps({"error": "Empty VLAN filter."})

    devices = parse_asset_db()
    q = vlan.lower()
    hits = [
        _record_summary(d)
        for d in devices
        if d.get("VLAN") and q in d["VLAN"].lower()
    ]

    return json.dumps({
        "vlan": vlan,
        "count": len(hits),
        "results": hits,
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def list_devices_by_category(category: str) -> str:
    """All devices in a section: Server, LXC, RasPi, Office, SmartHome, Entertainment, Network, Unknown.

    Match is a case-insensitive substring (e.g. "raspi" matches "RasPi",
    "smart" matches "SmartHome").

    Args:
        category: category short name (see above).

    Returns:
        JSON with the list of devices in the category.
    """
    if not category.strip():
        return json.dumps({
            "error": "Empty category filter.",
            "valid_categories": sorted(set(CATEGORY_MAP.values())),
        })

    devices = parse_asset_db()
    q = category.lower()
    hits = [
        _record_summary(d)
        for d in devices
        if d.get("_category") and q in d["_category"].lower()
    ]

    return json.dumps({
        "category": category,
        "count": len(hits),
        "results": hits,
    }, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Friendly nudge if an explicit ASSET_DB_PATH points nowhere — otherwise
    # every tool would silently return an empty list.
    if "ASSET_DB_PATH" in os.environ and not ASSET_DB_PATH.exists():
        print(
            f"[homelab-asset-db-mcp] warning: ASSET_DB_PATH={ASSET_DB_PATH} "
            f"does not exist — tools will return empty results.",
            file=sys.stderr,
        )
    mcp.run()
