# Added to handle GSM Provider and GSM Signal Strength sensors in Home Assistant
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import SENSORS, COORDINATOR, DEVICE_INFO, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]
    device_info = hass.data[DOMAIN][config_entry.entry_id][DEVICE_INFO]
    sensors = []
    for sensor in SENSORS:
        sensors.append(ProtexialSensor(device_info, coordinator, sensor))
    async_add_entities(sensors)


class ProtexialSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Protexial sensor."""

    def __init__(self, device_info, coordinator, sensor: Any) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_id = f"{DOMAIN}_{sensor['id']}"
        self._attr_unique_id = f"{DOMAIN}_{sensor['id']}"
        self._attr_device_info = device_info
        self._sensor_id = sensor["id"]
        self._name = sensor["name"]
        self._icon = sensor.get("icon")
        self._device_class = sensor.get("device_class")
        self._native_value = None
        self._suggested_display_precision = sensor.get("suggested_display_precision")
        if "entity_category" in sensor:
            self._attr_entity_category = sensor["entity_category"]
        self._attr_suggested_display_precision = sensor.get("suggested_display_precision")

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return self._icon

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._native_value

    @property
    def suggested_display_precision(self):
        """Return the suggested display precision."""
        return self._suggested_display_precision

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data

        if data:
            # Access the value as an attribute of the Status object
            value = getattr(data, self._sensor_id, None)

            # Specific handling for RecGSM (integer conversion)
            if self._sensor_id == "recgsm" and value is not None:
                try:
                    self._native_value = int(value)
                except (ValueError, TypeError):
                    _LOGGER.warning("Could not convert value '%s' for sensor '%s' to integer", value, self._sensor_id)
                    self._native_value = None
            # Specific handling for OpeGSM (removing quotes)
            elif self._sensor_id == "opegsm" and value is not None:
                self._native_value = value.strip().replace('"', '')
            # General handling for other sensors
            else:
                self._native_value = value

        self.async_write_ha_state()