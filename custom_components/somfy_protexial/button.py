# Buttons (manual refresh, default/error acknowledgement, date/time sync)
import logging

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from .attribute_translations import get_attribute_localization
from .const import API, BUTTONS, COORDINATOR, DEVICE_INFO, DOMAIN
from .somfy_exception import SomfyException

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the button platform."""
    protexial = hass.data[DOMAIN][config_entry.entry_id][API]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]
    device_info = hass.data[DOMAIN][config_entry.entry_id][DEVICE_INFO]

    entities = [
        ProtexialRefreshButton(
            device_info=device_info,
            coordinator=coordinator,
            entry_id=config_entry.entry_id,
        )
    ]

    # Date/time synchronization uses the installer-only general settings page.
    # Keep the button hidden on installations where installer credentials have
    # not been configured, just like the per-element PAUSE switches.
    if protexial.installer_username and protexial.installer_password:
        entities.extend(
            [
                ProtexialReadDateTimeButton(
                    device_info=device_info,
                    protexial=protexial,
                    entry_id=config_entry.entry_id,
                ),
                ProtexialSyncTimeButton(
                    device_info=device_info,
                    protexial=protexial,
                    entry_id=config_entry.entry_id,
                ),
            ]
        )

    for button in BUTTONS:
        description = ButtonEntityDescription(
            key=button["id"],
            translation_key=button["translation_key"],
            icon=button.get("icon"),
            entity_category=EntityCategory.CONFIG,
        )
        entities.append(ProtexialResetButton(device_info, protexial, description))

    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.debug("No buttons to add.")


class ProtexialRefreshButton(ButtonEntity):
    """Button that manually refreshes all coordinator-backed entities."""

    _attr_has_entity_name = True
    _attr_translation_key = "refresh"
    _attr_icon = "mdi:refresh"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, device_info, coordinator, entry_id: str) -> None:
        """Initialize the manual refresh button."""
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry_id}_refresh"
        self._attr_device_info = device_info

    async def async_press(self) -> None:
        """Request an immediate refresh from the coordinator."""
        await self.coordinator.async_request_refresh()


class ProtexialReadDateTimeButton(ButtonEntity):
    """Read and expose the date/time currently stored in the centrale."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:clipboard-text-clock"
    _attr_entity_category = EntityCategory.CONFIG

    entity_description = ButtonEntityDescription(
        key="read_centrale_datetime",
        translation_key="read_centrale_datetime",
        icon="mdi:clipboard-text-clock",
        entity_category=EntityCategory.CONFIG,
    )

    def __init__(self, device_info, protexial, entry_id: str) -> None:
        """Initialize the date/time read button."""
        self._protexial = protexial
        self._entry_id = entry_id
        self._attr_unique_id = f"{entry_id}_read_centrale_datetime"
        self._attr_device_info = device_info
        self._centrale_datetime = None
        self._centrale_date = None
        self._centrale_time = None

    @property
    def extra_state_attributes(self):
        """Expose the last date/time read from the centrale."""
        labels = get_attribute_localization(self)["datetime_labels"]
        return {
            labels["datetime"]: self._centrale_datetime,
            labels["date"]: self._centrale_date,
            labels["time"]: self._centrale_time,
        }

    async def async_press(self) -> None:
        """Read a fresh date/time value from i_reggen.htm."""
        try:
            values = await self._protexial.get_centrale_datetime()
            self._centrale_date = (
                f"{values['date_dd']}/{values['date_mm']}/{values['date_yy']}"
            )
            self._centrale_time = f"{values['heure_hh']}:{values['heure_mm']}"
            self._centrale_datetime = f"{self._centrale_date} {self._centrale_time}"

            # Publish the freshly read value to the dedicated sensor.
            entry_data = self.hass.data[DOMAIN][self._entry_id]
            entry_data["centrale_datetime"] = self._centrale_datetime
            entry_data["centrale_date"] = self._centrale_date
            entry_data["centrale_time"] = self._centrale_time
            async_dispatcher_send(
                self.hass,
                f"{DOMAIN}_{self._entry_id}_centrale_datetime_updated",
            )
            _LOGGER.info(
                "Somfy centrale date/time read successfully: %s",
                self._centrale_datetime,
            )
            self.async_write_ha_state()
        except SomfyException as ex:
            _LOGGER.error("Failed to read Somfy centrale date/time: %s", ex)
            raise


class ProtexialSyncTimeButton(ButtonEntity):
    """Synchronize the centrale date/time with Home Assistant local time."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    entity_description = ButtonEntityDescription(
        key="sync_centrale_datetime",
        translation_key="sync_centrale_datetime",
        icon="mdi:calendar-sync",
        entity_category=EntityCategory.CONFIG,
    )

    def __init__(self, device_info, protexial, entry_id: str) -> None:
        """Initialize the date/time synchronization button."""
        self._protexial = protexial
        self._attr_unique_id = f"{entry_id}_sync_time"
        self._attr_device_info = device_info

    async def async_press(self) -> None:
        """Copy Home Assistant's local date/time to the Somfy centrale."""
        try:
            await self._protexial.sync_centrale_datetime(dt_util.now())
        except SomfyException as ex:
            _LOGGER.error("Failed to synchronize Somfy centrale date/time: %s", ex)
            raise


class ProtexialResetButton(ButtonEntity):
    """Button that acknowledges/resets one of the centrale's default flags."""

    _attr_has_entity_name = True

    def __init__(
        self, device_info, protexial, description: ButtonEntityDescription
    ) -> None:
        """Initialize a translated reset button."""
        self.entity_description = description
        self._attr_translation_key = description.translation_key
        self._protexial = protexial
        self._button_id = description.key
        self._attr_unique_id = f"{DOMAIN}_{self._button_id}"
        self._attr_device_info = device_info

    async def async_press(self) -> None:
        """Call the matching reset_xxx() coroutine on the API client."""
        method = getattr(self._protexial, self._button_id, None)
        if method is None:
            _LOGGER.error("No API method found for button '%s'", self._button_id)
            return
        try:
            await method()
        except SomfyException as ex:
            _LOGGER.error("Failed to reset default '%s': %s", self._button_id, ex)
            raise
