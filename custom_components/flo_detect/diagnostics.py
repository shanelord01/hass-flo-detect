"""Diagnostics for the Flo Detect integration."""

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import FloDetectConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: FloDetectConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "flo_entry_id": entry.data.get("flo_entry_id"),
        "devices": [
            {
                "device_id": coordinator.device_id,
                "last_update_success": coordinator.last_update_success,
                "last_reported_event_end": (
                    coordinator.last_end.isoformat() if coordinator.last_end else None
                ),
                "remembered_event_ids": coordinator.seen_count,
                "events_in_last_update": [
                    event.as_attributes() for event in coordinator.data or []
                ],
            }
            for coordinator in entry.runtime_data.coordinators
        ],
    }
