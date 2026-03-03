# NetAmp Home Assistant Custom Component (v0.2.0)

## Install
1. Copy `custom_components/netamp` into your Home Assistant `config/custom_components/`.
2. Restart Home Assistant.
3. Add integration: Settings → Devices & services → Add integration → **NetAmp**.

## Discovery
The config flow broadcasts UDP `IPNetAmp:0:FIND:` on port 30303 and lists responders.

## Entities
- `media_player.netamp_zone_1`, `media_player.netamp_zone_2`
- Numbers per zone: Max Volume, Bass, Treble, Balance
- Select per zone: LIM input (Auto / Analogue / Digital)
- Sensors: Zone 1/2 name, global source names (sn1/sn2/sn3/sn4/snl)

## Notes
- Polling uses `gpv` for both zones and `gpn` for names.
- Standby is tracked separately (src off => standby True, src on/selection => standby False).
