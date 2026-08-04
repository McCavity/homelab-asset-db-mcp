"""Tests for the homelab-asset-db-mcp parser and tools.

Runnable without pytest:  python3 -m unittest discover -s tests
(also works under pytest if available)

Covers the bundled English sample DB and a small inline German fixture, so a
change that breaks German-headed production databases fails here.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

# Import the server module from the repo root (one level up from tests/).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from server import (  # noqa: E402
    parse_asset_db,
    find_device,
    get_device,
    list_devices_by_vlan,
    list_devices_by_category,
)

SAMPLE = Path(__file__).resolve().parent.parent / "asset-db.sample.md"


class ParseSampleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.devices = parse_asset_db(SAMPLE)

    def test_sample_parses_to_devices(self) -> None:
        # 3 servers + 3 LXC + 2 Pis + 2 office + 3 smarthome + 2 entertainment
        # + 2 personal + 2 local services + 1 unknown = 20; Naming Scheme and
        # the Network pointer add nothing.
        self.assertEqual(len(self.devices), 20)

    def test_naming_scheme_section_skipped(self) -> None:
        for d in self.devices:
            self.assertNotEqual(d["_section"], "Naming Scheme")
        # No record should carry the naming-scheme "Field" column.
        self.assertFalse(any("Field" in d for d in self.devices))

    def test_network_pointer_yields_no_devices(self) -> None:
        self.assertFalse(
            any(d["_category"] == "Network" for d in self.devices)
        )

    def test_categories_present(self) -> None:
        cats = {d["_category"] for d in self.devices}
        self.assertEqual(
            cats,
            {"Server", "LXC", "RasPi", "Office", "SmartHome",
             "Entertainment", "Personal", "LocalService", "Unknown"},
        )

    def test_em_dash_normalized_to_absent(self) -> None:
        # Sensor Pi's "Services / URL" is "—" -> dropped in the summary.
        pi = next(d for d in self.devices if d.get("Hostname") == "pi-sensor")
        self.assertNotIn("Services / URL", {k: v for k, v in pi.items() if v})


class ToolTests(unittest.TestCase):
    """Tools call parse_asset_db() with no arg -> module default (the sample)."""

    def test_find_device_substring(self) -> None:
        res = json.loads(find_device("grafana"))
        self.assertEqual(res["count"], 1)
        self.assertEqual(res["results"][0]["Hostname"], "grafana01")

    def test_find_device_by_ip_prefix(self) -> None:
        res = json.loads(find_device("10.10.30"))
        # Smart Home VLAN block + the sensor Pi all share the 10.10.30.x prefix.
        self.assertGreaterEqual(res["count"], 3)

    def test_find_device_empty_query(self) -> None:
        self.assertIn("error", json.loads(find_device("   ")))

    def test_get_device_exact(self) -> None:
        res = json.loads(get_device("pve01"))
        self.assertEqual(res["Name"], "Proxmox Node 1")

    def test_get_device_is_not_substring(self) -> None:
        # "pve" must NOT match "pve01" (exact match only).
        self.assertIn("error", json.loads(get_device("pve")))

    def test_list_by_vlan_substring(self) -> None:
        # Three devices in the Smart Home section + the sensor Pi, which sits
        # on the Smart Home VLAN while living in the Raspberry Pis section.
        res = json.loads(list_devices_by_vlan("smart home"))
        self.assertEqual(res["count"], 4)

    def test_list_by_category(self) -> None:
        res = json.loads(list_devices_by_category("raspi"))
        self.assertEqual(res["count"], 2)

    def test_local_services_are_devices_not_prose(self) -> None:
        # A loopback-bound LaunchAgent is an asset like any other. Before this
        # category existed the section parsed to nothing at all -- silently.
        res = json.loads(list_devices_by_category("localservice"))
        self.assertEqual(res["count"], 2)

    def test_personal_devices_are_devices_not_prose(self) -> None:
        # Phones and laptops were skipped for the same reason local services
        # were: their heading was simply absent from CATEGORY_MAP.
        res = json.loads(list_devices_by_category("personal"))
        self.assertEqual(res["count"], 2)


class GermanProductionCompatTests(unittest.TestCase):
    """A German-headed DB (the real-world shape) must still parse."""

    GERMAN_DB = """# Asset-DB

## Server & Infrastruktur

| Name | IP | VLAN | Hostname | Typ | Notizen |
|---|---|---|---|---|---|
| Server Eins | 10.0.0.1 | HomeLab | srv01 | Proxmox | primär |

## Büro / Arbeitsplatz

| Name | IP | VLAN | Typ | Notizen |
|---|---|---|---|---|
| Drucker | 10.0.40.5 | Work | Brother | Duplex |

## Personal Devices / Apple

| Name | IP | VLAN | Typ | Notizen |
|---|---|---|---|---|
| Ein Telefon | 10.0.128.7 | Unrestricted | iPhone | statische private MAC |

## Lokale Dienste (macOS)

| Name | IP | VLAN | Hostname | Typ | Notizen |
|---|---|---|---|---|---|
| Mini-Dienst | 127.0.0.1:8799 | lokal | — | LaunchAgent | nur loopback |

## Klärungsbedarf

| Gerät | MAC | IP | Problem |
|---|---|---|---|
| Unbekannt | de:ad:be:ef:00:01 | 10.0.90.9 | nicht zugeordnet |
"""

    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        )
        self.tmp.write(self.GERMAN_DB)
        self.tmp.close()
        self.path = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.path.unlink(missing_ok=True)

    def test_german_headers_parse(self) -> None:
        devices = parse_asset_db(self.path)
        self.assertEqual(len(devices), 5)
        cats = {d["_category"] for d in devices}
        self.assertEqual(cats, {"Server", "Büro", "Personal", "LocalService", "Unknown"})

    def test_german_lookup_field(self) -> None:
        devices = parse_asset_db(self.path)
        printer = next(d for d in devices if d["_category"] == "Büro")
        self.assertEqual(printer["Name"], "Drucker")


class MissingFileTests(unittest.TestCase):
    def test_missing_file_returns_empty(self) -> None:
        self.assertEqual(parse_asset_db(Path("/nonexistent/asset-db.md")), [])


if __name__ == "__main__":
    unittest.main()
