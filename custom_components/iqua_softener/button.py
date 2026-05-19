import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.util import slugify
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .vendor.iqua_softener import IquaSoftenerException

from homeassistant import config_entries, core
from .const import DOMAIN, CONF_DEVICE_SERIAL_NUMBER, CONF_PRODUCT_SERIAL_NUMBER
from .sensor import IquaSoftenerCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Set up the Iqua Softener button platform."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    if config_entry.options:
        config.update(config_entry.options)

    # Get device serial number (prefer device_sn, fallback to product_sn)
    device_serial_number = config.get(CONF_DEVICE_SERIAL_NUMBER) or config.get(CONF_PRODUCT_SERIAL_NUMBER)
    if not device_serial_number:
        _LOGGER.error("No device or product serial number found in config for button setup")
        return

    # Use the shared coordinator from __init__.py
    coordinator = config["coordinator"]

    # Create the regeneration button
    buttons = [IquaSoftenerRegenerateButton(coordinator, device_serial_number)]
    _LOGGER.info("Start Regeneration button created for device %s", device_serial_number)

    async_add_entities(buttons)


class IquaSoftenerRegenerateButton(ButtonEntity, CoordinatorEntity):
    """Representation of the Iqua Softener start regeneration button."""

    coordinator: IquaSoftenerCoordinator  # Type hint override for proper attribute access

    def __init__(
        self,
        coordinator: IquaSoftenerCoordinator,
        device_serial_number: str,
    ):
        """Initialize the button."""
        super().__init__(coordinator)
        self._device_serial_number = device_serial_number
        self._attr_unique_id = f"{device_serial_number}_start_regeneration".lower()
        self._attr_name = "Start Regeneration"
        self._attr_icon = "mdi:reload"
        self.entity_id = f"button.{slugify(device_serial_number)}_start_regeneration"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success and self.coordinator.data is not None
        )

    async def async_press(self) -> None:
        """Handle the button press to start regeneration."""
        try:
            _LOGGER.info("Starting regeneration cycle for device %s", self._device_serial_number)
            await self.hass.async_add_executor_job(
                self.coordinator._iqua_softener.regenerate_now
            )
            _LOGGER.info("Regeneration cycle started successfully")
            # Request an immediate update after the action
            await self.coordinator.async_request_refresh()
        except IquaSoftenerException as err:
            _LOGGER.error("Failed to start regeneration: %s", err)
            raise

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._device_serial_number)},
            "name": f"Iqua Softener {self._device_serial_number}",
            "manufacturer": "Iqua",
            "model": "Water Softener",
        }
