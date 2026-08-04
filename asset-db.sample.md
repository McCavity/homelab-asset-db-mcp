# Homelab Asset DB (sample)

> Fictional example data — every device, IP, MAC and hostname here is made up.
> Copy this file, point `ASSET_DB_PATH` at your own copy, and fill in reality.
> The parser keys off the `## Section` headings below; sections it doesn't
> recognise (like "Naming Scheme") are treated as prose and skipped.

## Naming Scheme

This section is documentation, not devices — the server ignores it because
"Naming Scheme" is not in `CATEGORY_MAP`.

| Field | Example | Notes |
|---|---|---|
| Type (2 chars) | `ap` (Application), `db` (Database) | Almost always `ap` |
| Index | `01`, `02` | Per role |

## Server & Infrastructure

| Name | IP | VLAN | Hostname | Type | Notes |
|---|---|---|---|---|---|
| Proxmox Node 1 | 10.10.10.11 | HomeLab | pve01 | Proxmox VE | Ryzen 5, 64 GB RAM |
| Proxmox Node 2 | 10.10.10.12 | HomeLab | pve02 | Proxmox VE | Cluster peer |
| NAS | 10.10.10.20 | HomeLab | nas01 | TrueNAS | 4-bay, ZFS mirror |

## LXC Containers

| Name | IP | VLAN | Hostname | Service |
|---|---|---|---|---|
| Grafana | 10.10.10.31 | HomeLab | grafana01 | Grafana + InfluxDB |
| Paperless | 10.10.10.32 | HomeLab | paperless01 | Paperless-ngx |
| Reverse Proxy | 10.10.10.33 | HomeLab | proxy01 | Caddy |

## Raspberry Pis

| Name | IP | VLAN | Hostname | Function | Hardware | Services / URL |
|---|---|---|---|---|---|---|
| DNS Pi | 10.10.10.53 | HomeLab | pi-dns | Pi-hole DNS | Pi 4B 4 GB | http://pi-dns/admin |
| Sensor Pi | 10.10.30.54 | Smart Home | pi-sensor | Room sensors | Pi Zero 2 W | — |

## Network Infrastructure (UniFi)

Managed in the UniFi controller — see `network.md`. This section is a pointer
and carries no device table, so the parser yields nothing for it.

## Office / Workspace

| Name | IP | VLAN | Type | Notes |
|---|---|---|---|---|
| Desk Printer | 10.10.40.60 | Office | Mono Laser Printer | Duplex laser |
| Desk Phone | 10.10.40.61 | Office | SIP Desk Phone | SIP |

## Smart Home / IoT

| Name | IP | VLAN | Type | Room |
|---|---|---|---|---|
| Smart Plug | 10.10.30.70 | Smart Home | Wi-Fi Smart Plug | Living Room |
| Thermostat | 10.10.30.71 | Smart Home | Smart Thermostat | Bedroom |
| Bird Feeder Cam | 10.10.30.72 | Smart Home | Wi-Fi Camera | Garden |

## Personal Devices

> Phones, tablets and laptops. Track them by their static private MAC, not by
> the DHCP lease — the lease moves, the identifier should not.

| Name | IP | VLAN | Type | Notes |
|---|---|---|---|---|
| Owner Phone | 10.10.128.20 | Unrestricted | Phone | static private MAC `02:00:5e:10:00:01` |
| Owner Laptop | 10.10.128.21 | Unrestricted | Laptop | static private MAC `02:00:5e:10:00:02` |

## Local Services (macOS)

> LaunchAgents bound to `127.0.0.1` — not reachable from the LAN. Listed here
> because an unlisted local service is one nobody remembers running.

| Name | IP | VLAN | Hostname | Type | Notes |
|---|---|---|---|---|---|
| Metrics Console | 127.0.0.1:8765 | local | — | LaunchAgent | Label `com.example.metrics`; loopback only |
| Notes Dashboard | 127.0.0.1:8766 | local | — | LaunchAgent | Label `com.example.notes`; loopback only |

## Entertainment

| Name | IP | VLAN | Type | Room |
|---|---|---|---|---|
| Media Box | 10.10.50.80 | Entertainment | Android TV Box | Living Room |
| Internet Radio | 10.10.50.81 | Entertainment | Wi-Fi Internet Radio | Kitchen |

## Needs Clarification

| Device | MAC | IP | Problem |
|---|---|---|---|
| Unknown Wi-Fi client | aa:bb:cc:00:11:22 | 10.10.90.99 | Appears on Guest VLAN, not inventoried |
