"""Flo Detect water-use event entities."""

from typing import override

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import EVENT_TYPES, FLO_DOMAIN
from .coordinator import FloDetectConfigEntry, FloDetectDataUpdateCoordinator

PARALLEL_UPDATES = 0


def _flo_device(
    hass: HomeAssistant, coordinator: FloDetectDataUpdateCoordinator
) -> dr.DeviceEntry | None:
    """Return the device the Flo integration registered for this valve."""
    device_registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(
        device_registry, coordinator.flo_entry.entry_id
    ):
        if (FLO_DOMAIN, coordinator.device_id) in device.identifiers:
            return device
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FloDetectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Flo Detect event entities."""
    async_add_entities(
        FloDetectWaterUseEvent(coordinator, _flo_device(hass, coordinator))
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

    def __init__(
        self,
        coordinator: FloDetectDataUpdateCoordinator,
        flo_device: dr.DeviceEntry | None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac_address}_flo_detect_water_use"
        # Attach to the Flo integration's device for the valve. Device info with
        # the Flo identifier would create a separate device for this entry.
        # (In core Flo this entity subclasses FloEntity and uses its device info.)
        self.device_entry = flo_device

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
