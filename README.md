# NetAmp Home Assistant Custom Component

Local-polling Home Assistant integration for **Armour Home NetAmp** devices.

This integration provides:
- Device discovery via UDP broadcast.
- Per-zone media player control.
- Per-zone tone/limit numeric controls.
- Per-zone LIM input selection.
- Text sensors for zone and source names.
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
- Set absolute volume (0..30 internally, 0.0..1.0 in HA)
- Volume up/down steps
- Mute/unmute
- Select source

Selectable sources use dynamic names reported by the device when available:
- Source 1 (`sn1`)
- Source 2 (`sn2`)
- Source 3 (`sn3`)
- Local source (`snl`)

> **Note:** The NetAmp protocol defines sources 1, 2, 3, and Local as selectable inputs.
> "Source 3a" (`sn4`) is a MAC-addressed network stream variant of source 3; it appears
> as a name label in device responses but is not a separately addressable source.

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
  - Source 3a Name (`sn4`)
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

## Protocol / state behaviour notes

Each poll cycle issues the following commands sequentially:

| Command | Returns |
|---|---|
| `$g1gpv` | Zone 1 source, volume, balance, bass, treble |
| `$g2gpv` | Zone 2 source, volume, balance, bass, treble |
| `$g1gpn` | Zone 1 name, all source names |
| `$g2gpn` | Zone 2 name (source names are the same, zone is don't-care) |
| `$g1mxv` | Zone 1 max volume limit |
| `$g2mxv` | Zone 2 max volume limit |
| `$g1lim` | Zone 1 LIM input mode |
| `$g2lim` | Zone 2 LIM input mode |

> `mxv` and `lim` are not included in the `gpv` response so they are fetched separately.

**Standby / source state machine:**
- `src off` → standby `True`, `last_source` preserved
- Explicit source select (e.g. `src 1`) → standby `False`, `last_source` updated
- `src on` → standby `False`, last source restored (note: the device responds with the
  actual source rather than echoing `srcon`, so state is updated from the source response)

---

## Services

### `netamp.set_raw_command`
Send a raw NetAmp TCP command. Intended for debugging and protocol inspection.

Service fields:
- `entry_id` (required): config entry id
- `command` (required): command string, e.g. `$g1gpv`

Example:

```yaml
service: netamp.set_raw_command
data:
  entry_id: "0123456789abcdef0123456789abcdef"
  command: "$g1gpv"
```

A coordinator refresh is triggered after the command is sent so any state changes appear immediately.

### `netamp.set_bass`
Set bass for one zone or both zones at once.

Service fields:
- `entry_id` (required): config entry id
- `zone` (required): `"1"`, `"2"`, or `"X"` (apply to both zones)
- `level` (required): integer from `-7` to `7`

Example:

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

Example:

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

Example:

```yaml
service: netamp.set_balance
data:
  entry_id: "0123456789abcdef0123456789abcdef"
  zone: "2"
  level: 5
```

---

## Troubleshooting

### Device not discovered
- Ensure Home Assistant and NetAmp are on the same L2 broadcast domain/VLAN.
- Verify UDP broadcast is allowed on your network.
- Use manual host entry if discovery is blocked.

### Entity unavailable / stale values
- Confirm TCP connectivity from Home Assistant host to NetAmp (`9760` by default).
- Reduce scan interval if you need faster state updates; increase it if the device is sensitive to rapid polling.
- Check Home Assistant logs for `NetAmpProtocolError` or connection drops.

### Source naming
- Source names (`sn1`–`sn4`, `snl`) are global (zone is don't-care per spec) and are read from zone 1 and zone 2 `gpn` responses.
- If names look wrong, send `$g1gpn` via `set_raw_command` and inspect the responses in logs.

---

## Development notes

- Syntax check:
  ```bash
  python -m py_compile custom_components/netamp/*.py
  ```
- Run unit tests:
  ```bash
  python -m unittest discover -s tests -v
  ```
- Test coverage includes:
  - Source state transitions and `last_source` logic
  - Mute / unmute response parsing (`$r1mute`, `$r1moff`, and `vol`-prefixed variants)
  - Full `gpv` and `gpn` multi-line response parsing
  - `mxv` and `lim` response parsing
