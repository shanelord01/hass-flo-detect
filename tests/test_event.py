"""Tests for the Flo Detect event entity and coordinator."""

from datetime import timedelta
from types import SimpleNamespace
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.flo_detect.const import DOMAIN, UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import (
    DEVICE_ID,
    FLO_ENTRY_ID,
    MAC_ADDRESS,
    flo_detect_event,
    flo_detect_payload,
)

UNIQUE_ID = f"{MAC_ADDRESS}_flo_detect_water_use"


def _entity_id(hass: HomeAssistant) -> str:
    entity_id = er.async_get(hass).async_get_entity_id("event", DOMAIN, UNIQUE_ID)
    assert entity_id is not None
    return entity_id


async def _tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(UPDATE_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_first_run_reports_nothing_then_new_events(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    flo_client: SimpleNamespace,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Existing history is marked as seen; later events fire once each."""
    flo_client.flodetect.get_events.return_value = flo_detect_payload(
        flo_detect_event("old-1", 120), flo_detect_event("old-2", 60)
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = _entity_id(hass)
    assert hass.states.get(entity_id).state == "unknown"
    # The detector has no Flo Detect events and gets no entity.
    assert (
        len(
            er.async_entries_for_config_entry(er.async_get(hass), config_entry.entry_id)
        )
        == 1
    )

    flo_client.flodetect.get_events.return_value = flo_detect_payload(
        flo_detect_event("old-1", 120),
        flo_detect_event("old-2", 60),
        flo_detect_event("new-1", 2, label="Shower", gallons=7.3),
    )
    await _tick(hass, freezer)
    state = hass.states.get(entity_id)
    assert state.attributes["event_type"] == "shower"
    assert state.attributes["flo_event_id"] == "new-1"
    assert state.attributes["volume_litres"] == round(7.3 * 3.785411784, 2)
    fired_at = state.state

    # The same events again fire nothing.
    await _tick(hass, freezer)
    assert hass.states.get(entity_id).state == fired_at


async def test_running_use_waits_until_settled(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    flo_client: SimpleNamespace,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A use that ended moments ago is reported on a later poll."""
    flo_client.flodetect.get_events.return_value = flo_detect_payload(
        flo_detect_event("old-1", 30)
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    entity_id = _entity_id(hass)

    # Ends 55 s from now: at the next poll (61 s) it ended only 6 s earlier.
    running: dict[str, Any] = flo_detect_event("new-1", 0)
    running["endAt"] = (dt_util.utcnow() + timedelta(seconds=55)).isoformat()
    flo_client.flodetect.get_events.return_value = flo_detect_payload(
        flo_detect_event("old-1", 30), running
    )
    await _tick(hass, freezer)
    assert hass.states.get(entity_id).state == "unknown"

    # One poll later it has been over for longer than SETTLE_TIME.
    await _tick(hass, freezer)
    assert hass.states.get(entity_id).attributes.get("flo_event_id") == "new-1"


async def test_unknown_prediction_is_other(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    flo_client: SimpleNamespace,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A fixture label Flo adds later is reported as other with its label."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    flo_client.flodetect.get_events.return_value = flo_detect_payload(
        flo_detect_event("new-1", 2, label="Ice Maker")
    )
    await _tick(hass, freezer)
    state = hass.states.get(_entity_id(hass))
    assert state.attributes["event_type"] == "other"
    assert state.attributes["predicted_label"] == "Ice Maker"


async def test_restart_reports_events_missed_while_down(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    config_entry: MockConfigEntry,
    flo_client: SimpleNamespace,
) -> None:
    """Events after the stored marker fire when the entity is added."""
    hass_storage[f"{DOMAIN}.{MAC_ADDRESS}"] = {
        "version": 1,
        "minor_version": 1,
        "key": f"{DOMAIN}.{MAC_ADDRESS}",
        "data": {
            "last_end": (dt_util.utcnow() - timedelta(minutes=30)).isoformat(),
            "seen": ["before-restart"],
        },
    }
    flo_client.flodetect.get_events.return_value = flo_detect_payload(
        flo_detect_event("before-restart", 30),
        flo_detect_event("while-down", 10, label="Toilet"),
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(_entity_id(hass))
    assert state.attributes["flo_event_id"] == "while-down"
    assert state.attributes["event_type"] == "toilet"


async def test_not_ready_until_flo_loads(
    hass: HomeAssistant, config_entry: MockConfigEntry, flo_entry: MockConfigEntry
) -> None:
    """Setup retries while the Flo entry is not loaded."""
    flo_entry.mock_state(hass, ConfigEntryState.SETUP_RETRY)
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_entity_attaches_to_flo_device(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """The event entity sits on the Flo device and adds no device of its own."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    flo_device = device_registry.async_get_device(identifiers={("flo", DEVICE_ID)})
    entry = er.async_get(hass).async_get(_entity_id(hass))
    assert entry.device_id == flo_device.id
    assert flo_device.config_entries == {FLO_ENTRY_ID}
    assert not dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)


async def test_removes_device_left_by_old_version(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A device only this entry owns (created by 0.1.0) is removed on setup."""
    device_registry = dr.async_get(hass)
    stray = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("flo_detect", "stray")},
        name="Flo Detect (Flo account)",
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert device_registry.async_get(stray.id) is None
