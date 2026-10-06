"""Number platform for Somfy Protexial controls."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import API, COORDINATOR, DEVICE_INFO, DOMAIN, REFRESH_INTERVAL_STORE
from .somfy_exception import SomfyException

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    api = data[API]
    entities: list[NumberEntity] = [
        SomfyRefreshIntervalNumber(
            coordinator=data[COORDINATOR],
            entry=entry,
            device_info=data[DEVICE_INFO],
            store=data[REFRESH_INTERVAL_STORE],
        )
    ]

    if api.installer_username and api.installer_password:
        try:
            settings = await api.get_general_settings()
            if api.general_setting_supported("tempoentree"):
                entities.append(
                    SomfyEntryDelayNumber(
                        api=api,
                        device_info=data[DEVICE_INFO],
                        entry_id=entry.entry_id,
                        initial_value=settings.get("tempoentree", "30"),
                    )
                )
        except SomfyException as ex:
            _LOGGER.warning("Unable to load Somfy entry delay setting: %s", ex)

    async_add_entities(entities)


class SomfyRefreshIntervalNumber(NumberEntity):
    """Control the coordinator automatic refresh interval."""

    _attr_has_entity_name = True
    _attr_translation_key = "refresh_interval"
    _attr_icon = "mdi:timer-refresh-outline"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 0
    _attr_native_max_value = 86400
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, device_info, store) -> None:
        self._coordinator = coordinator
        self._entry = entry
        self._store = store
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry.entry_id}_refresh_interval"
        self._configured_interval = int(entry.data.get(CONF_SCAN_INTERVAL, 60))

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        stored = await self._store.async_load()
        if isinstance(stored, dict):
            stored = stored.get("value")
        try:
            interval = int(stored)
        except (TypeError, ValueError):
            interval = self._configured_interval
        if not self.native_min_value <= interval <= self.native_max_value:
            interval = self._configured_interval
        self._attr_native_value = interval
        self._apply_interval(interval)

    async def async_set_native_value(self, value: float) -> None:
        interval = int(value)
        self._attr_native_value = interval
        self._apply_interval(interval)
        await self._store.async_save({"value": interval})
        self.async_write_ha_state()

    def _apply_interval(self, interval: int) -> None:
        self._coordinator.update_interval = None if interval == 0 else timedelta(seconds=interval)
        if self._coordinator.data is not None:
            self._coordinator.async_set_updated_data(self._coordinator.data)


class SomfyEntryDelayNumber(NumberEntity):
    """Installer entry delay (tempoentree) in seconds."""

    _attr_has_entity_name = True
    _attr_translation_key = "entry_delay"
    _attr_icon = "mdi:timer-lock-outline"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 1
    _attr_native_max_value = 60
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_mode = NumberMode.BOX
    _attr_should_poll = False

    def __init__(self, api, device_info, entry_id: str, initial_value: str) -> None:
        self._api = api
        self._attr_unique_id = f"{entry_id}_general_tempoentree"
        self._attr_device_info = device_info
        try:
            self._attr_native_value = int(initial_value)
        except (TypeError, ValueError):
            self._attr_native_value = 30

    async def async_set_native_value(self, value: float) -> None:
        delay = int(value)
        if delay < 1 or delay > 60:
            raise ValueError("Entry delay must be between 1 and 60 seconds")
        await self._api.update_general_settings({"tempoentree": str(delay)})
        self._attr_native_value = delay
        self.async_write_ha_state()
