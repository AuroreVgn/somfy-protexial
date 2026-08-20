"""Switch platform for Somfy Protexial/Protexiom element pause control."""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import API, COORDINATOR, DEVICE_INFO, DOMAIN, REFRESH_ELEMENTS
from .somfy_exception import SomfyException

_LOGGER = logging.getLogger(__name__)


def _element_icon(element: dict, active: bool | None = True) -> str:
    """Return the appropriate icon for a Somfy element."""
    label = (element.get("label") or "").lower()
    name = (element.get("name") or "").lower()

    element_type = f"{label} {name}"
    paused = active is False

    if "vitre" in element_type:
        return "mdi:window-open-variant" if paused else "mdi:window-closed-variant"

    if "ouvt" in element_type:
        return "mdi:door-open" if paused else "mdi:door-closed"

    if "do gar" in element_type:
        return "mdi:garage-open-variant" if paused else "mdi:garage-variant"

    if "dm" in element_type:
        return "mdi:motion-sensor-off" if paused else "mdi:motion-sensor"

    if "fum" in element_type:
        return (
            "mdi:smoke-detector-variant-alert"
            if paused
            else "mdi:smoke-detector-variant"
        )

    if "sir ext" in element_type:
        return "mdi:home-sound-out-outline" if paused else "mdi:home-sound-out"

    if "sir" in element_type:
        return "mdi:bullhorn-outline" if paused else "mdi:bullhorn"

    if "clavier" in element_type or "cl lcd" in element_type:
        return "mdi:keyboard-off-outline" if paused else "mdi:dialpad"

    if "tc" in element_type:
        return "mdi:remote-off" if paused else "mdi:remote"

    if "badge" in element_type:
        return "mdi:key-alert" if paused else "mdi:key-variant"

    if "tr" in element_type:
        return "mdi:alpha-s-box-outline" if paused else "mdi:alpha-s-box"

    return "mdi:alert-rhombus-outline" if paused else "mdi:help-rhombus"


def _pause_state(element: dict) -> bool | None:
    """Return True when active, False when paused, None when unknown."""
    raw = str(element.get("pause") or "").strip().lower()
    if raw == "running":
        return True
    if raw == "paused":
        return False
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one active/paused switch for each element exposing pause state."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    api = data[API]
    coordinator = data[COORDINATOR]
    device_info = data[DEVICE_INFO]
    refresh_elements = data[REFRESH_ELEMENTS]

    # Existing installations do not have installer credentials until the user
    # explicitly configures them in the integration options. In that case we
    # simply expose no writable switches, leaving all existing behaviour intact.
    if not api.installer_username or not api.installer_password:
        _LOGGER.debug(
            "Installer credentials are not configured; element pause switches disabled"
        )
        return

    switches = []
    for element in (coordinator.data or {}).get("elements", []):
        if _pause_state(element) is None:
            continue
        switches.append(
            SomfyElementActiveSwitch(
                coordinator, api, element, device_info, refresh_elements
            )
        )

    async_add_entities(switches)


class SomfyElementActiveSwitch(CoordinatorEntity, SwitchEntity):
    """Represent whether one Somfy element is active or paused."""

    _attr_has_entity_name = True
    _attr_translation_key = "element_active"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, coordinator, api, element: dict, device_info, refresh_elements
    ) -> None:
        """Initialize an element active/paused switch."""
        super().__init__(coordinator)
        self._api = api
        self._refresh_elements = refresh_elements
        self._element = element
        self._code = str(element.get("code") or "").strip()
        label = str(element.get("label") or "").strip()
        name = str(element.get("name") or "").strip()
        element_name = " - ".join(part for part in (label, name) if part) or self._code

        self._attr_unique_id = f"{DOMAIN}_elt_{self._code}_active"
        self._attr_device_info = device_info
        self._attr_translation_placeholders = {"element": element_name}

    def _find_element(self) -> dict | None:
        """Find the latest payload for this element in coordinator data."""
        for element in (self.coordinator.data or {}).get("elements", []):
            if str(element.get("code") or "").strip() == self._code:
                return element
        return None

    @property
    def icon(self) -> str:
        """Return an icon matching the element type and pause state."""
        element = self._find_element() or self._element
        return _element_icon(element, _pause_state(element))

    @property
    def is_on(self) -> bool | None:
        """Return True when the element is active, False when paused."""
        element = self._find_element()
        if element is None:
            return None
        return _pause_state(element)

    async def _set_active(self, active: bool) -> None:
        """Change the element state only when a toggle is actually required."""
        current = self.is_on
        if current is None:
            raise SomfyException(
                f"Unable to determine current state for element {self._code}"
            )
        if current == active:
            return

        await self._api.set_element_active(self._code, active)

        # The normal coordinator only refreshes the elements list when the
        # global status changes (or while a door is open). A pause toggle does
        # not necessarily change status.xml, so refresh the elements explicitly
        # to make the switch reflect the result immediately.
        elements = await self._refresh_elements()

        refreshed = next(
            (
                element
                for element in elements
                if str(element.get("code") or "").strip() == self._code
            ),
            None,
        )
        refreshed_state = _pause_state(refreshed or {})

        new_data = {
            **(self.coordinator.data or {}),
            "elements": elements,
            "last_sync": dt_util.utcnow(),
        }
        self.coordinator.async_set_updated_data(new_data)

        if refreshed_state != active:
            raise SomfyException(
                f"Element {self._code} did not reach the requested state"
            )

    async def async_turn_on(self, **kwargs) -> None:
        """Reactivate the element."""
        await self._set_active(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Pause the element."""
        await self._set_active(False)
