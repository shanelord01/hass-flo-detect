"""Flo Detect water-use event entities."""

from typing import override

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import EVENT_TYPES, FLO_DOMAIN
from .coordinator import FloDetectConfigEntry, FloDetectDataUpdateCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FloDetectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Flo Detect event entities."""
    async_add_entities(
        FloDetectWaterUseEvent(coordinator)
        for coordinator in config_entry.runtime_data.coordinators
    )


class FloDetectWaterUseEvent(
    CoordinatorEntity[FloDetectDataUpdateCoordinator], EventEntity
):
    """Fires once per water use Flo Detect reports for a Flo device.

    The event type is Flo's fixture prediction. Flo predicts from the flow
    pattern alone, so treat it as a likelihood, not a fact.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "water_use"
    _attr_event_types = EVENT_TYPES

    def __init__(self, coordinator: FloDetectDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac_address}_flo_detect_water_use"
        # Attach to the device the Flo integration created.
        self._attr_device_info = DeviceInfo(
            identifiers={(FLO_DOMAIN, coordinator.device_id)}
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Fire the events of the first refresh, which ran before this entity existed.

        After a restart these are the uses that happened while Home Assistant
        was down.
        """
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Fire one event per newly reported water use, oldest first."""
        for flo_event in self.coordinator.data or []:
            self._trigger_event(flo_event.event_type, flo_event.as_attributes())
            self.async_write_ha_state()
