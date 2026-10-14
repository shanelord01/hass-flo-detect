"""Constants for the Flo Detect integration."""

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "flo_detect"
FLO_DOMAIN: Final = "flo"
LOGGER = logging.getLogger(__package__)

CONF_FLO_ENTRY_ID: Final = "flo_entry_id"

# Flo Detect has no push channel, so it is polled at the same rate the core Flo
# integration polls the device itself.
UPDATE_INTERVAL: Final = timedelta(seconds=60)

# Events requested per poll. One minute of normal household use is a handful of
# events; 50 also covers a Home Assistant restart of a few hours.
EVENT_FETCH_LIMIT: Final = 50

# An event is reported once it ended at least this long ago, so a use that is
# still running is never reported with a partial volume.
SETTLE_TIME: Final = timedelta(seconds=30)

# Events that arrive late (Flo can publish an event a few minutes after it
# ended) are still reported if they ended within this window of the newest
# reported event.
LATE_EVENT_WINDOW: Final = timedelta(hours=1)

# Event ids remembered to avoid reporting the same event twice.
SEEN_EVENT_LIMIT: Final = 500

GALLONS_TO_LITRES: Final = 3.785411784

# Flo water detectors ("pucks") have no flow sensor and no Flo Detect events.
DEVICE_TYPE_DETECTOR: Final = "puck_oem"

# Fixture types Flo Detect predicts, as event types. A prediction Flo adds later
# is reported as "other" with its own label in the attributes.
EVENT_TYPE_OTHER: Final = "other"
EVENT_TYPES: Final = [
    "faucet",
    "shower",
    "bathtub",
    "toilet",
    "appliance",
    "irrigation",
    "pool",
    EVENT_TYPE_OTHER,
]

STORAGE_VERSION: Final = 1
