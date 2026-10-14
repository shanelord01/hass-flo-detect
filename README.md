# Flo Detect for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories)
[![Validate](https://github.com/shanelord01/hass-flo-detect/actions/workflows/validate.yml/badge.svg)](https://github.com/shanelord01/hass-flo-detect/actions/workflows/validate.yml)
[![Tests](https://github.com/shanelord01/hass-flo-detect/actions/workflows/tests.yml/badge.svg)](https://github.com/shanelord01/hass-flo-detect/actions/workflows/tests.yml)

Adds **Flo Detect** water-use events to the Flo by Moen smart water shutoff in
Home Assistant. Each time water runs, Flo Detect records when it started and
stopped (to the second), how much was used, and which kind of fixture Flo thinks
it was: faucet, shower, toilet, appliance, irrigation and so on. This
integration turns every one of those records into an event in Home Assistant.

The built-in [Flo integration](https://www.home-assistant.io/integrations/flo/)
reports the flow rate once a minute, so a 20-second hand wash between two
readings is never seen. Flo Detect is calculated by Flo from the valve's own
high-rate measurements, so short uses, exact durations and exact volumes come
through.

It works alongside the built-in Flo integration and signs in through it. There
is nothing extra to sign in to and no password is stored twice.

## Requirements

- Home Assistant 2026.10 or newer.
- The built-in Flo integration set up for your Flo account.
- A Flo Smart Water Shutoff. Flo water detectors (pucks) have no flow sensor and
  are skipped.

Flo Detect events were available on a Flo account without a FloProtect plan when
this was written. If Flo limits them to FloProtect in future, the entity stays
empty rather than failing.

## Installation

### HACS

1. In HACS, open the menu and choose **Custom repositories**.
2. Add `https://github.com/shanelord01/hass-flo-detect` with the type
   **Integration**.
3. Find **Flo Detect** in HACS and download it.
4. Restart Home Assistant.

### Manual

Copy `custom_components/flo_detect` into the `custom_components` folder of your
Home Assistant configuration and restart Home Assistant.

## Configuration

Go to **Settings > Devices & services > Add integration**, search for
**Flo Detect** and pick your Flo account. One Flo Detect entry covers every
shutoff valve on that account.

## Entity

Each shutoff valve gets one event entity on its existing Flo device:

| Entity | Example id |
|---|---|
| Water use | `event.<device name>_water_use` |

The entity fires once per water use, a minute or two after the use ends. The
event type is Flo's fixture prediction:

| Event type | Flo label |
|---|---|
| `faucet` | Faucet |
| `shower` | Shower |
| `bathtub` | Bathtub |
| `toilet` | Toilet |
| `appliance` | Appliance (washing machine, dishwasher) |
| `irrigation` | Irrigation |
| `pool` | Pool |
| `other` | Any label Flo adds in future; its own label is kept in `predicted_label` |

Event attributes:

| Attribute | Meaning |
|---|---|
| `flo_event_id` | Flo's id for the use |
| `start`, `end` | When the water started and stopped (ISO 8601) |
| `duration` | Seconds the water ran |
| `volume_litres` | Litres used |
| `volume_gallons` | US gallons used, as Flo reports them |
| `predicted_id` | Flo's numeric fixture id |
| `predicted_label` | Flo's fixture label |

### Treat the fixture as a likelihood

Flo predicts the fixture from the flow pattern alone. It cannot see which room
the water was used in, and similar flows are easily confused (a long faucet run
and a low-flow shower, for example). The timing and volume are measured; the
fixture is a guess. Combine it with other signals, such as room presence,
humidity or appliance power, rather than acting on it alone.

### Example automation

```yaml
triggers:
  - trigger: state
    entity_id: event.shasam_water_use
conditions:
  - condition: state
    entity_id: event.shasam_water_use
    attribute: event_type
    state: shower
actions:
  - action: notify.notify
    data:
      message: >
        Shower: {{ trigger.to_state.attributes.duration | int }} s,
        {{ trigger.to_state.attributes.volume_litres }} L.
```

## How it works

- Flo Detect is polled every 60 seconds, the same rate the Flo integration polls
  the valve.
- A use is reported once it has been over for 30 seconds, so a running use is
  never reported with a partial volume.
- On the first run the existing history is marked as seen and nothing is fired.
- The newest reported use and recent event ids are stored. After a restart, the
  uses that happened while Home Assistant was down (up to 50) are fired once,
  oldest first, and nothing is fired twice.
- A use that Flo publishes a few minutes late is still reported if it ended
  within an hour of the newest reported use.
- **Diagnostics** (on the integration page) show the last update, the newest
  reported use and how many event ids are remembered.

## Moving into the core Flo integration

The code is laid out so it can be merged into
`homeassistant/components/flo`:

| This integration | In core Flo |
|---|---|
| `coordinator.py`: `FloDetectEvent`, `FloDetectDataUpdateCoordinator` | Add to `coordinator.py`; build one detect coordinator per valve in `async_setup_entry` and keep them in `FloRuntimeData` |
| `event.py`: `FloDetectWaterUseEvent` | New `event.py` platform; add `Platform.EVENT` to `PLATFORMS`; subclass `FloEntity` for the device info |
| `__init__.py` lookup of the Flo entry | Not needed: use `runtime_data.client` directly instead of `flo_entry.runtime_data.client` |
| `strings.json`, `icons.json` (`water_use`) | Merge into the Flo `strings.json` and `icons.json` |
| `diagnostics.py` | Merge into Flo diagnostics |
| `tests/` | Port to `tests/components/flo/`, replacing the stand-in Flo entry with the existing Flo fixtures |

The library side is already in aioflo 2026.9.4
(`client.flodetect.get_events`), the version the core Flo integration uses.

## Development

```bash
python3.14 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/pytest
```

Pull requests run Hassfest, the HACS validation, Ruff and the tests.

## Licence

Apache License 2.0, the same licence as Home Assistant core. See
[LICENSE](LICENSE).

Not affiliated with or endorsed by Moen or Flo Technologies. Flo, Flo Detect and
FloProtect are trademarks of their owners.
