"""Select platform for Somfy Protexial installer sound-level settings."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import API, DEVICE_INFO, DOMAIN
from .somfy_exception import SomfyException

_LOGGER = logging.getLogger(__name__)

_LEVEL_TO_VALUE = {
    "low": "0",
    "medium": "1",
    "high": "3",
}
_VALUE_TO_LEVEL = {value: label for label, value in _LEVEL_TO_VALUE.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up installer sound-level selects."""
    data = hass.data[DOMAIN][entry.entry_id]
    api = data[API]
    if not api.installer_username or not api.installer_password:
        return

    entities: list[SelectEntity] = []
    try:
        settings = await api.get_general_settings()
        if api.general_setting_supported("biplevel"):
            entities.append(
                SomfySoundLevelSelect(
                    api=api,
                    device_info=data[DEVICE_INFO],
                    entry_id=entry.entry_id,
                    field="biplevel",
                    translation_key="siren_beep_level",
                    icon="mdi:volume-medium",
                    initial_value=settings.get("biplevel", "0"),
                )
            )
        if api.general_setting_supported("sirenlevel"):
            entities.append(
                SomfySoundLevelSelect(
                    api=api,
                    device_info=data[DEVICE_INFO],
                    entry_id=entry.entry_id,
                    field="sirenlevel",
                    translation_key="siren_level",
                    icon="mdi:bullhorn-outline",
                    initial_value=settings.get("sirenlevel", "3"),
                )
            )
    except SomfyException as ex:
        _LOGGER.warning("Unable to load Somfy siren level settings: %s", ex)

    async_add_entities(entities)


class SomfySoundLevelSelect(SelectEntity):
    """Sound level selector backed by i_reggen.htm."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_should_poll = False
    _attr_options = list(_LEVEL_TO_VALUE)

    def __init__(
        self,
        api,
        device_info,
        entry_id: str,
        field: str,
        translation_key: str,
        icon: str,
        initial_value: str,
    ) -> None:
        self._api = api
        self._field = field
        self._attr_translation_key = translation_key
        self._attr_icon = icon
        self._attr_unique_id = f"{entry_id}_general_{field}"
        self._attr_device_info = device_info
        self._attr_current_option = _VALUE_TO_LEVEL.get(str(initial_value), "low")

    async def async_select_option(self, option: str) -> None:
        if option not in _LEVEL_TO_VALUE:
            raise ValueError(f"Unsupported sound level: {option}")
        await self._api.update_general_settings(
            {self._field: _LEVEL_TO_VALUE[option]}
        )
        self._attr_current_option = option
        self.async_write_ha_state()
