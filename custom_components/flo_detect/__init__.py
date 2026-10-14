"""The Flo Detect integration.

Reports Flo Detect water-use events for the Flo devices of an existing Flo
config entry. It signs in through that entry's API client, so it needs no
credentials of its own.
"""

import asyncio

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import CONF_FLO_ENTRY_ID, DEVICE_TYPE_DETECTOR, DOMAIN, LOGGER
from .coordinator import (
    FloDetectConfigEntry,
    FloDetectDataUpdateCoordinator,
    FloDetectRuntimeData,
)

PLATFORMS = [Platform.EVENT]


async def async_setup_entry(hass: HomeAssistant, entry: FloDetectConfigEntry) -> bool:
    """Set up Flo Detect from a config entry."""
    flo_entry = hass.config_entries.async_get_entry(entry.data[CONF_FLO_ENTRY_ID])
    if flo_entry is None:
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="flo_entry_missing"
        )
    if flo_entry.state is not ConfigEntryState.LOADED:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="flo_not_loaded"
        )

    coordinators: list[FloDetectDataUpdateCoordinator] = []
    for device in flo_entry.runtime_data.devices:
        try:
            device_type = device.device_type
            mac_address = device.mac_address
        except KeyError:
            LOGGER.debug("Skipping Flo device %s: no device information yet", device.id)
            continue
        if device_type == DEVICE_TYPE_DETECTOR:
            continue
        coordinator = FloDetectDataUpdateCoordinator(
            hass, entry, flo_entry, device.id, mac_address
        )
        await coordinator.async_load_state()
        coordinators.append(coordinator)

    await asyncio.gather(
        *(
            coordinator.async_config_entry_first_refresh()
            for coordinator in coordinators
        )
    )

    entry.runtime_data = FloDetectRuntimeData(coordinators=coordinators)
    _async_remove_own_devices(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _async_remove_own_devices(hass: HomeAssistant, entry: FloDetectConfigEntry) -> None:
    """Detach this entry from devices only it owns.

    The entities attach to the Flo integration's devices and this entry owns
    none of its own. Version 0.1.0 created a duplicate device per valve; this
    removes it.
    """
    device_registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if device.config_entries == {entry.entry_id}:
            device_registry.async_update_device(
                device.id, remove_config_entry_id=entry.entry_id
            )


async def async_unload_entry(hass: HomeAssistant, entry: FloDetectConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: FloDetectConfigEntry) -> None:
    """Remove the stored event state of a removed config entry."""
    flo_entry = hass.config_entries.async_get_entry(entry.data[CONF_FLO_ENTRY_ID])
    if flo_entry is None or flo_entry.state is not ConfigEntryState.LOADED:
        return
    for device in flo_entry.runtime_data.devices:
        try:
            mac_address = device.mac_address
        except KeyError:
            continue
        await FloDetectDataUpdateCoordinator(
            hass, entry, flo_entry, device.id, mac_address
        ).async_remove_store()
