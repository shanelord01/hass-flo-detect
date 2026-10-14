"""Tests for the Flo Detect config flow."""

from unittest.mock import AsyncMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.flo_detect.const import CONF_FLO_ENTRY_ID, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import FLO_ENTRY_ID


async def test_abort_without_flo(hass: HomeAssistant) -> None:
    """The flow stops when no Flo entry is loaded."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "flo_not_loaded"


async def test_create_entry(
    hass: HomeAssistant, flo_entry: MockConfigEntry, mock_setup_entry: AsyncMock
) -> None:
    """Picking the Flo entry creates a Flo Detect entry for it."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_FLO_ENTRY_ID: FLO_ENTRY_ID}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Flo Detect (Flo account)"
    assert result["data"] == {CONF_FLO_ENTRY_ID: FLO_ENTRY_ID}
    assert result["result"].unique_id == FLO_ENTRY_ID


async def test_abort_when_already_configured(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_setup_entry: AsyncMock
) -> None:
    """A Flo entry gets only one Flo Detect entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_FLO_ENTRY_ID: FLO_ENTRY_ID}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
