import logging
from datetime import datetime

from homeassistant.components.datetime import DateTimeEntity

from .const import DOMAIN
from .naming import display_name_from_raw, legacy_entity_id, room_device_info

_LOGGER = logging.getLogger(__name__)


class DryingStartDateTime(DateTimeEntity):
    """Start of the running drying mode (drying.mode_start_time).

    The DataStore is the source of truth, so there is no separate state to restore.
    The DataStore keeps a naive local timestamp (datetime.now()), HA needs an aware one.
    """

    _attr_has_entity_name = False
    _attr_should_poll = True

    def __init__(self, name, room_name, coordinator):
        self._name = name
        self._attr_name = display_name_from_raw(name, room_name)
        self.room_name = room_name
        self.coordinator = coordinator
        self._unique_id = f"{DOMAIN}_{room_name}_{name.lower().replace(' ', '_')}"
        self.entity_id = legacy_entity_id("datetime", name)

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def name(self):
        return self._attr_name

    @property
    def device_info(self):
        return room_device_info(self.room_name, "DateTime Device")

    @property
    def native_value(self):
        start = self.coordinator.OGB.dataStore.getDeep("drying.mode_start_time")
        if not start:
            return None
        try:
            parsed = datetime.fromisoformat(start) if isinstance(start, str) else start
        except ValueError:
            _LOGGER.warning(f"Invalid drying.mode_start_time '{start}'")
            return None
        return parsed.astimezone()

    async def async_set_value(self, value: datetime) -> None:
        """Set the start of the drying mode, e.g. to continue a run after switching modes."""
        local_naive = value.astimezone().replace(tzinfo=None)
        ogb = self.coordinator.OGB
        ogb.dataStore.setDeep("drying.mode_start_time", local_naive.isoformat())
        await ogb.eventManager.emit("SaveState", {"source": "DryingStart"})
        self.async_write_ha_state()
        _LOGGER.debug(f"Drying start '{self._name}' set to {local_naive.isoformat()}")


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the drying start datetime entity."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        [
            DryingStartDateTime(
                f"OGB_DryingStart_{coordinator.room_name}",
                coordinator.room_name,
                coordinator,
            )
        ]
    )
