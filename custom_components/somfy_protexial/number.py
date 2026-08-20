"""Number platform for Somfy Protexial refresh interval control."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components.number import NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import COORDINATOR, DEVICE_INFO, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the refresh interval number entity."""
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            SomfyRefreshIntervalNumber(
                coordinator=data[COORDINATOR],
                entry=entry,
                device_info=data[DEVICE_INFO],
            )
        ]
    )


class SomfyRefreshIntervalNumber(RestoreNumber):
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

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry: ConfigEntry,
        device_info,
    ) -> None:
        """Initialize the refresh interval entity."""
        self._coordinator = coordinator
        self._entry = entry
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry.entry_id}_refresh_interval"
        self._configured_interval = int(entry.data.get(CONF_SCAN_INTERVAL, 60))

    async def async_added_to_hass(self) -> None:
        """Restore the last effective interval after reload or restart."""
        await super().async_added_to_hass()

        restored = await self.async_get_last_number_data()
        if restored is not None and restored.native_value is not None:
            interval = int(restored.native_value)
            # Ignore a stale/corrupt restored value outside the supported range.
            if not self.native_min_value <= interval <= self.native_max_value:
                interval = self._configured_interval
        else:
            interval = self._configured_interval

        self._attr_native_value = interval
        self._apply_interval(interval)

    async def async_set_native_value(self, value: float) -> None:
        """Set the effective automatic refresh interval."""
        interval = int(value)
        self._attr_native_value = interval
        self._apply_interval(interval)
        self.async_write_ha_state()

    def _apply_interval(self, interval: int) -> None:
        """Apply the interval and immediately reschedule coordinator polling."""
        self._coordinator.update_interval = (
            None if interval == 0 else timedelta(seconds=interval)
        )

        # Changing DataUpdateCoordinator.update_interval alone does not replace an
        # already scheduled timer. Re-setting its current data safely cancels the
        # old timer and schedules the next refresh with the new interval, without
        # making an additional request to the alarm panel.
        if self._coordinator.data is not None:
            self._coordinator.async_set_updated_data(self._coordinator.data)
