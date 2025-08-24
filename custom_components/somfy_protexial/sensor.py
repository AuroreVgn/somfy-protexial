# Sensors (GSM + zones from elements)
import logging
from typing import Any, Iterable

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


# ---------- Utils ----------
def _collect_zone_options(elements: Iterable[dict]) -> list[str]:
    """Build an enum options list from actually observed zones."""
    zones = {e.get("zone", "") for e in (elements or []) if e.get("zone")}
    # keep stable order: SYS first, then alpha
    ordered = ["SYS"] + sorted(z for z in zones if z != "SYS")
    return ordered or ["SYS"]


def _find_element_by_code(elements: list[dict], code: str) -> dict | None:
    """Find an element dict by its 'code' field."""
    for e in elements or []:
        if e.get("code") == code:
            return e
    return None


# ---------- Setup ----------
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform (GSM sensors + optional per-element zone sensor)."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]
    device_info = hass.data[DOMAIN][config_entry.entry_id][DEVICE_INFO]

    entities: list[SensorEntity] = []

    # 1) Predefined sensors in SENSORS (GSM provider, signal, etc.)
    for sensor in SENSORS:
        entities.append(ProtexialSensor(device_info, coordinator, sensor))

    # 2) Per-element zone sensors (ENUM) from u_plistelmt.htm (kept commented by design)
    elements = (coordinator.data or {}).get("elements", [])
    zone_options = _collect_zone_options(elements)

    # for el in elements:
    #     # Create a unique 'zone' sensor per element
    #     code = el.get("code")
    #     name = el.get("name")
    #     label = el.get("label")
    #     if not code:
    #         continue
    #     entities.append(
    #         SomfyElementZoneSensor(
    #             element_code=code,
    #             element_label=label or "",
    #             element_name=name or "",
    #             device_info=device_info,
    #             coordinator=coordinator,
    #             options=zone_options,
    #         )
    #     )

    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.debug("No sensors to add (SENSORS + zones).")


# ---------- Existing sensors (GSM, etc.) ----------
class ProtexialSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Protexial sensor (e.g., GSM operator, RecGSM)."""

    def __init__(self, device_info, coordinator, sensor: Any) -> None:
        """Build the entity using static sensor metadata and the coordinator."""
        super().__init__(coordinator)
        self._attr_id = f"{DOMAIN}_{sensor['id']}"
        self._attr_unique_id = f"{DOMAIN}_{sensor['id']}"
        self._attr_device_info = device_info
        self._sensor_id = sensor["id"]
        self._name = sensor["name"]
        self._icon = sensor.get("icon")
        self._device_class = sensor.get("device_class")
        self._native_value = None
        self._suggested_display_precision = sensor.get(
            "suggested_display_precision")
        if "entity_category" in sensor:
            self._attr_entity_category = sensor["entity_category"]
        self._attr_suggested_display_precision = sensor.get(
            "suggested_display_precision"
        )

    @property
    def name(self):
        """Entity name."""
        return self._name

    @property
    def icon(self):
        """Entity icon."""
        return self._icon

    @property
    def device_class(self):
        """Device class (if any)."""
        return self._device_class

    @property
    def native_value(self):
        """Native value exposed to HA."""
        return self._native_value

    @property
    def suggested_display_precision(self):
        """Suggested display precision for numeric sensors."""
        return self._suggested_display_precision

    def _handle_coordinator_update(self) -> None:
        """Handle updated coordinator data."""
        data = self.coordinator.data
        if data:
            # For these sensors, data comes from status.xml (dictified Status)
            value = (data or {}).get(self._sensor_id)

            # recgsm -> int conversion
            if self._sensor_id == "recgsm" and value is not None:
                try:
                    self._native_value = int(value)
                except (ValueError, TypeError):
                    _LOGGER.warning(
                        "Could not convert value '%s' for sensor '%s' to integer",
                        value,
                        self._sensor_id,
                    )
                    self._native_value = None
            # opegsm -> strip quotes
            elif self._sensor_id == "opegsm" and value is not None:
                self._native_value = str(value).replace('"', "").strip()
            else:
                self._native_value = value

        self.async_write_ha_state()


# ---------- Per-element zone sensors (commented) ----------
# class SomfyElementZoneSensor(CoordinatorEntity, SensorEntity):
#     """ENUM zone sensor based on u_plistelmt.htm for a given element."""
#
#     _attr_device_class = SensorDeviceClass.ENUM
#
#     def __init__(
#         self,
#         element_code: str,
#         element_label: str,
#         element_name: str,
#         device_info,
#         coordinator,
#         options: list[str],
#     ):
#         """Build the per-element zone sensor."""
#         super().__init__(coordinator)
#         self._code = element_code
#         self._label = element_label
#         self._name_part = element_name
#         self._attr_name = f"{element_label} - {element_name} (zone)".strip(" -")
#         self._attr_unique_id = f"{DOMAIN}_element_zone_{element_code}"
#         self._attr_device_info = device_info
#         self._attr_options = options
#         self._native_value = None  # updated on refresh
#
#     @property
#     def native_value(self):
#         """Return the current zone value."""
#         return self._native_value
#
#     def _handle_coordinator_update(self) -> None:
#         """Pick up the current zone from coordinator.data['elements']."""
#         payload = self.coordinator.data or {}
#         elements = payload.get("elements", [])
#         el = _find_element_by_code(elements, self._code)
#         new_zone = el.get("zone") if el else None
#
#         # If a new value shows up, add it to options
#         if new_zone and isinstance(self._attr_options, list) and new_zone not in self._attr_options:
#             self._attr_options = self._attr_options + [new_zone]
#
#         self._native_value = new_zone
#         self.async_write_ha_state()
