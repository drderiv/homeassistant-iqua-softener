"""Select entities for iQua Softener device settings."""
import logging
from typing import Any, Optional, cast

from homeassistant.components.select import SelectEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .vendor.iqua_softener import IquaSoftenerData, IquaSoftenerException

from homeassistant import config_entries, core
from .const import DOMAIN, CONF_DEVICE_SERIAL_NUMBER, CONF_PRODUCT_SERIAL_NUMBER
from .sensor import IquaSoftenerCoordinator

_LOGGER = logging.getLogger(__name__)


# Mapping of setting names to their display information
SETTING_INFO = {
    "salt_type": {
        "name": "Salt Type",
        "icon": "mdi:salt",
    },
    "inlet_hardness": {
        "name": "Inlet Water Hardness",
        "icon": "mdi:water",
    },
    "regeneration_time": {
        "name": "Regeneration Time",
        "icon": "mdi:clock",
    },
    "efficiency_mode": {
        "name": "Efficiency Mode",
        "icon": "mdi:leaf",
    },
    "max_days_between_recharges": {
        "name": "Max Days Between Recharges",
        "icon": "mdi:calendar",
    },
    "feature_97_percent": {
        "name": "97% Feature",
        "icon": "mdi:alert-circle",
    },
}


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Set up the Iqua Softener select platform."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    if config_entry.options:
        config.update(config_entry.options)

    # Get device serial number (prefer device_sn, fallback to product_sn)
    device_serial_number = config.get(CONF_DEVICE_SERIAL_NUMBER) or config.get(CONF_PRODUCT_SERIAL_NUMBER)
    if not device_serial_number:
        _LOGGER.error("No device or product serial number found in config for select setup")
        return

    # Use the shared coordinator from __init__.py
    coordinator = config["coordinator"]

    if coordinator.data is None:
        _LOGGER.warning("No data available from coordinator")
        return

    # Fetch device settings
    try:
        settings_data = await hass.async_add_executor_job(
            coordinator._iqua_softener.get_device_settings  # type: ignore
        )
        settings = settings_data.get("settings", [])
    except Exception as err:
        _LOGGER.error("Failed to fetch device settings: %s", err)
        return

    # Create select entities for configurable settings
    select_entities = []
    for setting in settings:
        setting_name = setting.get("name")
        if setting_name not in SETTING_INFO:
            continue

        component_type = setting.get("component_type")
        if component_type != "select":
            continue

        select_rules = setting.get("rules", {}).get("select_rules", {})
        options = select_rules.get("options", [])
        if not options:
            continue

        current_value = setting.get("current_value", "")
        
        select_entities.append(
            IquaSoftenerSelectSetting(
                coordinator,
                device_serial_number,
                setting_name,
                setting.get("label", setting_name),
                options,
                current_value,
            )
        )

    if select_entities:
        _LOGGER.info("Created %d device setting select entities", len(select_entities))
        async_add_entities(select_entities)
    else:
        _LOGGER.info("No configurable device settings found")


class IquaSoftenerSelectSetting(SelectEntity, CoordinatorEntity):
    """Representation of an iQua Softener device setting."""

    coordinator: IquaSoftenerCoordinator

    def __init__(
        self,
        coordinator: IquaSoftenerCoordinator,
        device_serial_number: str,
        setting_name: str,
        setting_label: str,
        options: list,
        current_value: str,
    ):
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._device_serial_number = device_serial_number
        self._setting_name = setting_name
        self._setting_label = setting_label
        self._options = options
        self._current_value = current_value

        # Build list of option labels for Home Assistant
        self._option_labels = [opt.get("label", opt.get("value")) for opt in options]
        self._option_values = [opt.get("value") for opt in options]

        # Generate unique_id
        self._attr_unique_id = f"{device_serial_number}_setting_{setting_name}".lower()
        
        # Set entity name
        self._attr_name = setting_label
        
        # Set icon from SETTING_INFO if available
        info = SETTING_INFO.get(setting_name, {})
        self._attr_icon = info.get("icon", "mdi:cog")
        
        # Set current value
        self._update_current_value()

    def _update_current_value(self):
        """Update the current value based on stored value."""
        if self._current_value in self._option_values:
            idx = self._option_values.index(self._current_value)
            self._attr_current_option = self._option_labels[idx]
        else:
            self._attr_current_option = None

    @property
    def options(self) -> list[str]:
        """Return list of available options."""
        return self._option_labels

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success and self.coordinator.data is not None
        )

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        try:
            # Find the value corresponding to this option label
            if option not in self._option_labels:
                _LOGGER.error(
                    "Invalid option %s for setting %s", option, self._setting_name
                )
                return

            idx = self._option_labels.index(option)
            setting_value = self._option_values[idx]

            _LOGGER.info(
                "Setting %s to %s (value: %s)",
                self._setting_name,
                option,
                setting_value,
            )

            # Call the API to update the setting
            await self.hass.async_add_executor_job(
                self.coordinator._iqua_softener.set_device_setting,  # type: ignore
                self._setting_name,
                setting_value,
            )

            # Update local state
            self._current_value = setting_value
            self._update_current_value()
            self.async_write_ha_state()

            # Refresh coordinator to get updated data
            await self.coordinator.async_request_refresh()

        except IquaSoftenerException as err:
            _LOGGER.error(
                "Failed to set device setting %s: %s", self._setting_name, err
            )
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
