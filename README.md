# NetAmp Home Assistant Custom Component

Local-polling Home Assistant integration for **Armour Home NetAmp** devices.

This integration provides:
- Device discovery via UDP broadcast.
- Per-zone media player control.
- Per-zone tone/limit numeric controls.
- Per-zone LIM input selection.
- Text sensors for zone and global source names.
- Dedicated services for zone bass/treble/balance control.
- A debug raw-command service for protocol troubleshooting.

---

## Features

### Media Player (per zone)
Each configured amplifier exposes:
- `media_player.netamp_zone_1`
- `media_player.netamp_zone_2`

Supported actions:
- Turn on / off (`srcon` / `srcoff`)
- Set absolute volume (0..30 internally)
- Volume up/down steps
- Mute/unmute
- Select source

Source list uses dynamic names reported by the device when available:
- Source 1 (`sn1`)
- Source 2 (`sn2`)
- Source 3 (`sn3`)
- Source 4 (`sn4`)
- Local source (`snl`)

### Number Entities (per zone)
- Max Volume (`mxv`, 0..30)
- Bass (`bas`, -7..7)
- Treble (`tre`, -7..7)
- Balance (`bal`, -15..15)

### Select Entities (per zone)
- LIM Input (`lim`):
  - Auto (`1`)
  - Analogue (`a`)
  - Digital (`d`)

### Sensor Entities
- Per zone:
  - Zone Name (`znn`)
- Global source-name sensors:
  - Source 1 Name (`sn1`)
  - Source 2 Name (`sn2`)
  - Source 3 Name (`sn3`)
  - Source 4 Name (`sn4`)
  - Local Source Name (`snl`)

---

## Installation

### HACS
1. Add this repository as a custom repository in HACS: https://github.com/holdestmade/netamp-home-assistant
2. In Home Assistant, open HACS → Integrations, find NetAmp and install.
3. Restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration**.
5. Search for **NetAmp**.
   
### Manual installation
1. Copy `custom_components/netamp` into:
   ```
   <home-assistant-config>/custom_components/netamp
   ```
2. Restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration**.
4. Search for **NetAmp**.

---

## Configuration

### Discovery mode (recommended)
During setup, the config flow broadcasts:
- UDP port: `30303`
- Payload: `IPNetAmp:0:FIND:`

Detected devices are shown in the UI for one-click setup.

### Manual mode
If discovery does not find your unit, choose **Manual entry** and provide:
- Host/IP
- TCP port (default `9760`)

### Options
After setup, configure:
- `scan_interval` (seconds)
  - Minimum: `2`
  - Maximum: `300`
  - Default: `10`

---

## Protocol/state behavior notes

- Polling cycle fetches:
  - Zone 1 values (`$g1gpv`)
  - Zone 2 values (`$g2gpv`)
  - Name data (`$g1gpn`)
- `standby` is tracked from source state transitions:
  - `src off` → standby `True`
  - `src on` or explicit source selection → standby `False`
- `last_source` is tracked so `srcon`/`src on` can restore meaningful source context.
- Integration currently parses zone/global response lines matching `$r...` protocol format.

---

## Services

### `netamp.set_raw_command`
Send a raw NetAmp TCP command for debugging.

Service fields:
- `entry_id` (required): config entry id
- `command` (required): command string, e.g. `$g1gpv`

Validation rules:
- Must not be empty
- Max length: 64 characters
- Must start with `$`
- Allowed characters: `A-Z`, `a-z`, `0-9`, `+`, `-`

Example service call:

```yaml
service: netamp.set_raw_command
data:
  entry_id: "0123456789abcdef0123456789abcdef"
  command: "$g1gpv"
```

> This service is intended for debugging and protocol inspection.

### `netamp.set_bass`
Set bass for one zone or both zones at once.

Service fields:
- `entry_id` (required): config entry id
- `zone` (required): `"1"`, `"2"`, or `"X"` (apply to both zones)
- `level` (required): integer from `-7` to `7`

Example service call:

```yaml
service: netamp.set_bass
data:
  entry_id: "0123456789abcdef0123456789abcdef"
  zone: "X"
  level: 2
```

### `netamp.set_treble`
Set treble for one zone or both zones at once.

Service fields:
- `entry_id` (required): config entry id
- `zone` (required): `"1"`, `"2"`, or `"X"` (apply to both zones)
- `level` (required): integer from `-7` to `7`

Example service call:

```yaml
service: netamp.set_treble
data:
  entry_id: "0123456789abcdef0123456789abcdef"
  zone: "1"
  level: -3
```

### `netamp.set_balance`
Set balance for one zone or both zones at once.

Service fields:
- `entry_id` (required): config entry id
- `zone` (required): `"1"`, `"2"`, or `"X"` (apply to both zones)
- `level` (required): integer from `-15` to `15`

Example service call:

```yaml
service: netamp.set_balance
data:
  entry_id: "0123456789abcdef0123456789abcdef"
  zone: "2"
  level: 5
```

> These service calls trigger a coordinator refresh after the command is sent.

---

## Troubleshooting

### Device not discovered
- Ensure Home Assistant and NetAmp are on the same L2 broadcast domain/VLAN.
- Verify UDP broadcast is allowed on your network.
- Use manual host entry if discovery is blocked.

### Entity unavailable / stale values
- Confirm TCP connectivity from Home Assistant host to NetAmp (`9760` by default).
- Increase scan interval if the device is sensitive to rapid polling.
- Check Home Assistant logs for `NetAmpProtocolError` or connection drops.

### Source naming oddities
- Some names are global and may be returned on zone 1 name polling.
- If names look wrong, send `$g1gpn` via `set_raw_command` and inspect responses in logs.

---

## Development notes

- Python module compiles cleanly via:
  ```bash
  python -m py_compile custom_components/netamp/*.py
  ```
- Parser behavior for source transitions is covered by unit tests in:
  - `tests/test_netamp_source_parsing.py`
