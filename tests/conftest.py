"""Fixtures for the Flo Detect tests."""

from collections.abc import Generator
from datetime import timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.flo_detect.const import CONF_FLO_ENTRY_ID, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

FLO_ENTRY_ID = "flo-entry-1"
DEVICE_ID = "device-1"
MAC_ADDRESS = "d4e95ef75e58"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load custom integrations in every test."""


def flo_detect_event(
    event_id: str, minutes_ago: float, *, label: str = "Faucet", gallons: float = 0.2
) -> dict[str, Any]:
    """Return one event in the shape of the Flo Detect API."""
    end = dt_util.utcnow() - timedelta(minutes=minutes_ago)
    start = end - timedelta(seconds=20)
    return {
        "id": event_id,
        "startAt": start.isoformat(),
        "endAt": end.isoformat(),
        "totalGal": gallons,
        "duration": 20.0,
        "macAddress": MAC_ADDRESS,
        "predicted": {"id": 300, "displayText": label},
    }


def flo_detect_payload(*events: dict[str, Any]) -> dict[str, Any]:
    """Wrap events the way the API groups them per device."""
    return {
        "params": {"macAddress": MAC_ADDRESS},
        "items": [{"macAddress": MAC_ADDRESS, "events": list(events)}],
    }


@pytest.fixture
def flo_client() -> SimpleNamespace:
    """Return a stand-in for the aioflo API client of the Flo entry."""
    return SimpleNamespace(
        flodetect=SimpleNamespace(
            get_events=AsyncMock(return_value=flo_detect_payload())
        )
    )


@pytest.fixture
def flo_entry(hass: HomeAssistant, flo_client: SimpleNamespace) -> MockConfigEntry:
    """Return a loaded Flo config entry with one shutoff valve and one detector."""
    entry = MockConfigEntry(
        domain="flo",
        entry_id=FLO_ENTRY_ID,
        title="Flo account",
        data={"username": "user@example.com", "password": "secret"},
        state=ConfigEntryState.LOADED,
    )
    entry.add_to_hass(hass)
    entry.runtime_data = SimpleNamespace(
        client=flo_client,
        devices=[
            SimpleNamespace(
                id=DEVICE_ID, mac_address=MAC_ADDRESS, device_type="flo_device_v2"
            ),
            SimpleNamespace(
                id="detector-1", mac_address="aabbccddeeff", device_type="puck_oem"
            ),
        ],
    )
    return entry


@pytest.fixture
def config_entry(hass: HomeAssistant, flo_entry: MockConfigEntry) -> MockConfigEntry:
    """Return the Flo Detect config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FLO_ENTRY_ID,
        title="Flo Detect (Flo account)",
        data={CONF_FLO_ENTRY_ID: FLO_ENTRY_ID},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Stub out entry setup for config flow tests."""
    with patch(
        "custom_components.flo_detect.async_setup_entry", return_value=True
    ) as mock:
        yield mock
