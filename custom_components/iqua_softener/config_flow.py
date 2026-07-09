import logging
from typing import Any, Dict, Optional

from homeassistant import config_entries
import voluptuous as vol

from .vendor.iqua_softener import IquaSoftener, IquaSoftenerException
from .const import (
    DOMAIN,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_DEVICE_SERIAL_NUMBER,
    CONF_PRODUCT_SERIAL_NUMBER,
    CONF_UPDATE_INTERVAL,
    CONF_ENABLE_WEBSOCKET,
    CONF_API_TYPE,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_ENABLE_WEBSOCKET,
    DEFAULT_API_TYPE,
    API_TYPE_IQUA,
    API_TYPE_IQUA2,
    API_URLS,
)

_LOGGER = logging.getLogger(__name__)

CONF_SELECTED_DEVICE = "selected_device"

DATA_SCHEMA_USER = vol.Schema(
    {
        vol.Required(CONF_API_TYPE, default=DEFAULT_API_TYPE): vol.In(
            [API_TYPE_IQUA, API_TYPE_IQUA2]
        ),
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=60)
        ),
        vol.Optional(CONF_ENABLE_WEBSOCKET, default=DEFAULT_ENABLE_WEBSOCKET): bool,
    }
)


def _property_value(device: Dict[str, Any], *names: str) -> Optional[str]:
    """Return a device property value from either root fields or properties."""
    properties = device.get("properties", {})
    for name in names:
        value = device.get(name)
        if value is None and isinstance(properties, dict):
            value = properties.get(name)
        if isinstance(value, dict):
            value = value.get("value") or value.get("converted_value")
        if value not in (None, ""):
            return str(value)
    return None


def _device_serial(device: Dict[str, Any]) -> Optional[str]:
    return _property_value(
        device,
        "serial_number",
        "device_serial_number",
        "device_sn",
        "serialNumber",
    )


def _product_serial(device: Dict[str, Any]) -> Optional[str]:
    return _property_value(
        device,
        "product_serial_number",
        "product_sn",
        "productSerialNumber",
    )


def _device_name(device: Dict[str, Any]) -> Optional[str]:
    return _property_value(device, "name", "nickname", "device_name", "label")


def _device_model(device: Dict[str, Any]) -> Optional[str]:
    return _property_value(device, "model", "product_name", "product_model")


def _device_label(device: Dict[str, Any]) -> str:
    """Build a readable label for the Home Assistant device picker."""
    name = _device_name(device)
    serial = _device_serial(device)
    product_serial = _product_serial(device)
    model = _device_model(device)

    title = name or model or "iQua Softener"
    identifiers = []
    if serial:
        identifiers.append(f"SN {serial}")
    if product_serial and product_serial != serial:
        identifiers.append(f"Product {product_serial}")

    if identifiers:
        return f"{title} ({', '.join(identifiers)})"

    device_id = device.get("id") or device.get("device_id")
    if device_id:
        return f"{title} ({device_id})"

    return title


def _device_key(device: Dict[str, Any], index: int) -> str:
    """Return a stable-ish key for this flow's transient device choices."""
    return str(
        device.get("id")
        or device.get("device_id")
        or _device_serial(device)
        or _product_serial(device)
        or index
    )


def _device_title(device: Dict[str, Any]) -> str:
    serial = _device_serial(device) or _product_serial(device)
    if serial:
        return f"iQua Device {serial}"
    return _device_label(device)


class IquaSoftenerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    data: Optional[Dict[str, Any]]
    _devices: Dict[str, Dict[str, Any]]
    VERSION = 3

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        errors: Dict[str, str] = {}
        if user_input is not None:
            discovery_result = await self._discover_devices(user_input)

            if discovery_result["success"]:
                self.data = dict(user_input)
                self._devices = discovery_result["devices"]
                return await self.async_step_device()
            else:
                errors["base"] = discovery_result["error"]

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA_USER,
            errors=errors,
        )

    async def async_step_device(self, user_input: Optional[Dict[str, Any]] = None):
        """Let the user choose which discovered device to add."""
        errors: Dict[str, str] = {}

        if not hasattr(self, "context"):
            self.context = {}

        if getattr(self, "data", None) is None or not getattr(self, "_devices", None):
            return await self.async_step_user()

        if user_input is not None:
            selected_key = user_input[CONF_SELECTED_DEVICE]
            selected_device = self._devices[selected_key]
            data = {
                key: value
                for key, value in self.data.items()
                if key not in (CONF_DEVICE_SERIAL_NUMBER, CONF_PRODUCT_SERIAL_NUMBER)
            }

            device_sn = _device_serial(selected_device)
            product_sn = _product_serial(selected_device)

            if device_sn:
                data[CONF_DEVICE_SERIAL_NUMBER] = device_sn
            if product_sn:
                data[CONF_PRODUCT_SERIAL_NUMBER] = product_sn

            if not device_sn and not product_sn:
                errors["base"] = "device_missing_serial_number"
            elif getattr(self, "context", {}).get("entry_id"):
                config_entry = self.hass.config_entries.async_get_entry(
                    self.context["entry_id"]
                )
                if config_entry is None:
                    errors["base"] = "invalid_entry"
                else:
                    existing_data = {
                        key: value
                        for key, value in config_entry.data.items()
                        if key
                        not in (
                            CONF_DEVICE_SERIAL_NUMBER,
                            CONF_PRODUCT_SERIAL_NUMBER,
                        )
                    }
                    updated_data = {**existing_data, **data}
                    return self.async_update_reload_and_abort(
                        config_entry,
                        data=updated_data,
                        unique_id=device_sn or product_sn,
                    )
            else:
                await self.async_set_unique_id(device_sn or product_sn)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=_device_title(selected_device),
                    data=data,
                )

        options = {
            device_key: _device_label(device)
            for device_key, device in self._devices.items()
        }
        schema = vol.Schema({vol.Required(CONF_SELECTED_DEVICE): vol.In(options)})

        return self.async_show_form(
            step_id="device",
            data_schema=schema,
            errors=errors,
        )

    async def _discover_devices(self, user_input: Dict[str, Any]) -> Dict[str, Any]:
        """Validate credentials and return devices available to the account."""
        try:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            api_type = user_input.get(CONF_API_TYPE, DEFAULT_API_TYPE)
            api_url = API_URLS.get(api_type, API_URLS[DEFAULT_API_TYPE])

            _LOGGER.info(
                "Discovering iQua devices for user: %s using %s API",
                username,
                api_type,
            )

            test_iqua = IquaSoftener(
                username=username,
                password=password,
                api_base_url=api_url,
                enable_websocket=False,
            )

            devices = await self.hass.async_add_executor_job(test_iqua.get_devices)
            device_options: Dict[str, Dict[str, Any]] = {}

            for index, device in enumerate(devices):
                if not _device_serial(device) and not _product_serial(device):
                    _LOGGER.debug(
                        "Skipping discovered iQua device without serial numbers: %s",
                        device,
                    )
                    continue

                key = _device_key(device, index)
                if key in device_options:
                    key = f"{key}_{index}"
                device_options[key] = device

            if not device_options:
                _LOGGER.error("No iQua devices with serial numbers were returned")
                return {"success": False, "error": "no_devices"}

            _LOGGER.info("Discovered %d iQua device(s)", len(device_options))
            return {"success": True, "devices": device_options, "error": None}

        except IquaSoftenerException as err:
            error_msg = str(err).lower()
            _LOGGER.error("iQua device discovery failed: %s", err)

            if (
                "authentication error" in error_msg
                or "invalid email or password" in error_msg
            ):
                return {"success": False, "error": "invalid_auth"}
            else:
                return {"success": False, "error": "cannot_connect"}

        except Exception as err:
            _LOGGER.error("Unexpected error during iQua device discovery: %s", err)
            error_msg = str(err).lower()
            if any(
                token in error_msg
                for token in ("connection", "connect", "timeout", "http")
            ):
                return {"success": False, "error": "cannot_connect"}
            return {"success": False, "error": "unknown"}

    async def async_step_reconfigure(self, user_input: Optional[Dict[str, Any]] = None):
        """Handle reconfiguration of the integration."""
        entry_id = self.context.get("entry_id")
        if entry_id is None:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=DATA_SCHEMA_USER,
                errors={"base": "invalid_entry"},
            )
        config_entry = self.hass.config_entries.async_get_entry(entry_id)
        errors: Dict[str, str] = {}

        if config_entry is None:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=DATA_SCHEMA_USER,
                errors={"base": "invalid_entry"},
            )

        if user_input is not None:
            discovery_result = await self._discover_devices(user_input)

            if discovery_result["success"]:
                self.data = dict(user_input)
                self._devices = discovery_result["devices"]
                return await self.async_step_device()
            else:
                errors["base"] = discovery_result["error"]

        # Pre-fill form with existing data
        current_data = config_entry.data
        default_schema = vol.Schema(
            {
                vol.Required(
                    CONF_API_TYPE,
                    default=current_data.get(CONF_API_TYPE, DEFAULT_API_TYPE),
                ): vol.In([API_TYPE_IQUA, API_TYPE_IQUA2]),
                vol.Required(CONF_USERNAME, default=current_data.get(CONF_USERNAME, "")): str,
                vol.Required(CONF_PASSWORD, default=current_data.get(CONF_PASSWORD, "")): str,
                vol.Optional(
                    CONF_UPDATE_INTERVAL,
                    default=current_data.get(
                        CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
                vol.Optional(
                    CONF_ENABLE_WEBSOCKET,
                    default=current_data.get(
                        CONF_ENABLE_WEBSOCKET, DEFAULT_ENABLE_WEBSOCKET
                    ),
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=default_schema,
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        return IquaSoftenerOptionsFlowHandler()


class IquaSoftenerOptionsFlowHandler(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_UPDATE_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_UPDATE_INTERVAL,
                        self.config_entry.data.get(
                            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                        ),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
                vol.Optional(
                    CONF_ENABLE_WEBSOCKET,
                    default=self.config_entry.options.get(
                        CONF_ENABLE_WEBSOCKET,
                        self.config_entry.data.get(
                            CONF_ENABLE_WEBSOCKET, DEFAULT_ENABLE_WEBSOCKET
                        ),
                    ),
                ): bool,
            }
        )

        return self.async_show_form(step_id="init", data_schema=options_schema)
