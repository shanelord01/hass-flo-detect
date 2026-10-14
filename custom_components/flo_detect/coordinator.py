"""Flo Detect event coordinator."""

import asyncio
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, override

from aioflo.errors import RequestError
from aioflo.flodetect import Flodetect

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    EVENT_FETCH_LIMIT,
    EVENT_TYPE_OTHER,
    EVENT_TYPES,
    GALLONS_TO_LITRES,
    LATE_EVENT_WINDOW,
    LOGGER,
    SEEN_EVENT_LIMIT,
    SETTLE_TIME,
    STORAGE_VERSION,
    UPDATE_INTERVAL,
)

type FloDetectConfigEntry = ConfigEntry[FloDetectRuntimeData]


@dataclass
class FloDetectRuntimeData:
    """Flo Detect runtime data."""

    coordinators: list[FloDetectDataUpdateCoordinator]


@dataclass(frozen=True, slots=True)
class FloDetectEvent:
    """One water use reported by Flo Detect."""

    event_id: str
    start: datetime
    end: datetime
    duration: float
    gallons: float
    predicted_id: int | None
    predicted_label: str | None

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> FloDetectEvent | None:
        """Build an event from the API payload, or None when it is incomplete."""
        start = dt_util.parse_datetime(raw.get("startAt") or "")
        end = dt_util.parse_datetime(raw.get("endAt") or "")
        if not raw.get("id") or start is None or end is None:
            return None
        predicted = raw.get("predicted") or {}
        return cls(
            event_id=str(raw["id"]),
            start=start,
            end=end,
            duration=float(raw.get("duration") or (end - start).total_seconds()),
            gallons=float(raw.get("totalGal") or 0),
            predicted_id=predicted.get("id"),
            predicted_label=predicted.get("displayText"),
        )

    @property
    def litres(self) -> float:
        """Return the volume in litres."""
        return self.gallons * GALLONS_TO_LITRES

    @property
    def event_type(self) -> str:
        """Return the event type for Flo's fixture prediction."""
        label = (self.predicted_label or "").strip().lower().replace(" ", "_")
        return label if label in EVENT_TYPES else EVENT_TYPE_OTHER

    def as_attributes(self) -> dict[str, Any]:
        """Return the event attributes."""
        return {
            "flo_event_id": self.event_id,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "duration": round(self.duration, 1),
            "volume_litres": round(self.litres, 2),
            "volume_gallons": round(self.gallons, 3),
            "predicted_id": self.predicted_id,
            "predicted_label": self.predicted_label,
        }


class FloDetectDataUpdateCoordinator(DataUpdateCoordinator[list[FloDetectEvent]]):
    """Fetch new Flo Detect events for one Flo device.

    Each refresh returns only the events not reported before, oldest first. The
    newest reported event and the recent event ids are stored, so a restart
    reports what happened while Home Assistant was down instead of repeating
    or losing it. On the very first run nothing is reported: the existing
    history is marked as seen.
    """

    config_entry: FloDetectConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: FloDetectConfigEntry,
        flo_entry: ConfigEntry,
        device_id: str,
        mac_address: str,
    ) -> None:
        """Initialize the coordinator."""
        self.flo_entry = flo_entry
        self.device_id = device_id
        self.mac_address = mac_address
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{mac_address}"
        )
        self._last_end: datetime | None = None
        self._seen: OrderedDict[str, None] = OrderedDict()
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}-{device_id}",
            update_interval=UPDATE_INTERVAL,
        )

    async def async_load_state(self) -> None:
        """Load the newest reported event and the seen event ids."""
        stored = await self._store.async_load() or {}
        self._last_end = dt_util.parse_datetime(stored.get("last_end") or "")
        self._seen = OrderedDict.fromkeys(stored.get("seen") or [])

    @property
    def last_end(self) -> datetime | None:
        """Return when the newest reported event ended."""
        return self._last_end

    @property
    def seen_count(self) -> int:
        """Return how many event ids are remembered."""
        return len(self._seen)

    def _api_client(self) -> Any:
        """Return the Flo API client of the Flo config entry."""
        if self.flo_entry.state is not ConfigEntryState.LOADED:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="flo_not_loaded"
            )
        return self.flo_entry.runtime_data.client

    def _remember(self, event_id: str) -> None:
        self._seen[event_id] = None
        self._seen.move_to_end(event_id)
        while len(self._seen) > SEEN_EVENT_LIMIT:
            self._seen.popitem(last=False)

    def _stored_state(self) -> dict[str, Any]:
        return {
            "last_end": self._last_end.isoformat() if self._last_end else None,
            "seen": list(self._seen),
        }

    @override
    async def _async_update_data(self) -> list[FloDetectEvent]:
        """Fetch Flo Detect events and return the ones not reported yet."""
        client = self._api_client()
        try:
            async with asyncio.timeout(20):
                payload = await client.flodetect.get_events(
                    self.mac_address, limit=EVENT_FETCH_LIMIT
                )
        except (RequestError, TimeoutError) as error:
            raise UpdateFailed(error) from error

        events = sorted(
            (
                event
                for event in map(
                    FloDetectEvent.from_api, Flodetect.parse_events(payload)
                )
                if event is not None
            ),
            key=lambda event: event.start,
        )
        cutoff = dt_util.utcnow() - SETTLE_TIME
        settled = [event for event in events if event.end <= cutoff]

        if self._last_end is None:
            for event in settled:
                self._remember(event.event_id)
            if settled:
                self._last_end = max(event.end for event in settled)
            self._store.async_delay_save(self._stored_state, 5)
            LOGGER.debug(
                "First Flo Detect fetch for %s: %s existing events marked as seen",
                self.mac_address,
                len(settled),
            )
            return []

        floor = self._last_end - LATE_EVENT_WINDOW
        new_events = [
            event
            for event in settled
            if event.event_id not in self._seen and event.end > floor
        ]
        for event in new_events:
            self._remember(event.event_id)
            self._last_end = max(self._last_end, event.end)
        if new_events:
            self._store.async_delay_save(self._stored_state, 5)
        return new_events

    async def async_remove_store(self) -> None:
        """Remove the stored state when the config entry is removed."""
        await self._store.async_remove()
