"""Test the iQua Softener config flow."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.data_entry_flow import FlowResultType

from custom_components.iqua_softener import config_flow
from custom_components.iqua_softener.const import (
    DOMAIN,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_DEVICE_SERIAL_NUMBER,
    CONF_PRODUCT_SERIAL_NUMBER,
    CONF_UPDATE_INTERVAL,
    CONF_ENABLE_WEBSOCKET,
    CONF_API_TYPE,
)
from custom_components.iqua_softener.vendor.iqua_softener import IquaSoftenerException


DEVICE = {
    "id": "device-id-1",
    "properties": {
        "name": {"value": "Basement Softener"},
        "serial_number": {"value": "DEVICE123"},
        "product_serial_number": {"value": "PRODUCT456"},
        "model": {"value": "Test Model"},
    },
}


class FakeConfigEntries:
    """Minimal config entries manager for config-flow unit tests."""

    def __init__(self, entry=None):
        self.entry = entry

    def async_get_entry(self, entry_id):
        return self.entry if self.entry and self.entry.entry_id == entry_id else None

    def async_entry_for_domain_unique_id(self, domain, unique_id):
        return None


def make_flow(entry=None):
    """Create a config flow with a lightweight fake hass object."""
    flow = config_flow.IquaSoftenerConfigFlow()
    flow.hass = SimpleNamespace(
        async_add_executor_job=AsyncMock(side_effect=lambda func: func()),
        config_entries=FakeConfigEntries(entry),
    )
    flow.context = {}
    flow.flow_id = "test-flow-id"
    flow.handler = DOMAIN
    return flow


def run(coro):
    """Run a config-flow coroutine without invoking pytest-asyncio fixtures."""
    return asyncio.get_event_loop().run_until_complete(coro)


class TestIquaSoftenerConfigFlow:
    """Test the iQua Softener config flow."""

    def test_user_flow_discovers_then_selects_device(self):
        """Test successful user flow with discovered device selection."""
        flow = make_flow()

        with patch.object(flow, "_discover_devices") as mock_discover:
            mock_discover.return_value = {
                "success": True,
                "devices": {"device-id-1": DEVICE},
                "error": None,
            }

            result = run(
                flow.async_step_user(
                    {
                        CONF_API_TYPE: "iqua",
                        CONF_USERNAME: "test@example.com",
                        CONF_PASSWORD: "password123",
                        CONF_UPDATE_INTERVAL: 10,
                        CONF_ENABLE_WEBSOCKET: False,
                    }
                )
            )

        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == "device"

        with (
            patch.object(flow, "async_set_unique_id", new=AsyncMock()) as mock_unique,
            patch.object(flow, "_abort_if_unique_id_configured") as mock_abort,
        ):
            result = run(
                flow.async_step_device(
                    {config_flow.CONF_SELECTED_DEVICE: "device-id-1"}
                )
            )

        assert result.get("type") == FlowResultType.CREATE_ENTRY
        assert result.get("title") == "iQua Device DEVICE123"
        assert result.get("data", {}).get(CONF_USERNAME) == "test@example.com"
        assert result.get("data", {}).get(CONF_DEVICE_SERIAL_NUMBER) == "DEVICE123"
        assert result.get("data", {}).get(CONF_PRODUCT_SERIAL_NUMBER) == "PRODUCT456"
        assert result.get("data", {}).get(CONF_UPDATE_INTERVAL) == 10
        assert result.get("data", {}).get(CONF_ENABLE_WEBSOCKET) is False
        mock_unique.assert_awaited_once_with("DEVICE123")
        mock_abort.assert_called_once()

    def test_user_flow_uses_product_serial_when_device_serial_missing(self):
        """Test user flow stores product serial when no device serial is returned."""
        flow = make_flow()
        product_only = {
            "id": "device-id-2",
            "properties": {"product_serial_number": {"value": "PRODUCT456"}},
        }

        flow.data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password123",
        }
        flow._devices = {"device-id-2": product_only}

        with (
            patch.object(flow, "async_set_unique_id", new=AsyncMock()) as mock_unique,
            patch.object(flow, "_abort_if_unique_id_configured") as mock_abort,
        ):
            result = run(
                flow.async_step_device(
                    {config_flow.CONF_SELECTED_DEVICE: "device-id-2"}
                )
            )

        assert result.get("type") == FlowResultType.CREATE_ENTRY
        assert result.get("title") == "iQua Device PRODUCT456"
        assert result.get("data", {}).get(CONF_PRODUCT_SERIAL_NUMBER) == "PRODUCT456"
        assert CONF_DEVICE_SERIAL_NUMBER not in result.get("data", {})
        mock_unique.assert_awaited_once_with("PRODUCT456")
        mock_abort.assert_called_once()

    def test_user_flow_discovery_failure(self):
        """Test user flow with discovery failure."""
        flow = make_flow()

        with patch.object(flow, "_discover_devices") as mock_discover:
            mock_discover.return_value = {"success": False, "error": "invalid_auth"}

            result = run(
                flow.async_step_user(
                    {
                        CONF_USERNAME: "test@example.com",
                        CONF_PASSWORD: "wrongpassword",
                    }
                )
            )

        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == "user"
        errors = result.get("errors")
        assert errors is not None and errors.get("base") == "invalid_auth"

    def test_discover_devices_success(self):
        """Test successful device discovery."""
        flow = make_flow()

        with patch(
            "custom_components.iqua_softener.config_flow.IquaSoftener"
        ) as mock_iqua_class:
            mock_iqua_instance = MagicMock()
            mock_iqua_instance.get_devices.return_value = [DEVICE]
            mock_iqua_class.return_value = mock_iqua_instance

            result = run(
                flow._discover_devices(
                    {
                        CONF_USERNAME: "test@example.com",
                        CONF_PASSWORD: "password123",
                    }
                )
            )

        assert result["success"] is True
        assert result["error"] is None
        assert list(result["devices"]) == ["device-id-1"]

    def test_discover_devices_no_devices(self):
        """Test discovery when no devices are returned."""
        flow = make_flow()

        with patch(
            "custom_components.iqua_softener.config_flow.IquaSoftener"
        ) as mock_iqua_class:
            mock_iqua_instance = MagicMock()
            mock_iqua_instance.get_devices.return_value = []
            mock_iqua_class.return_value = mock_iqua_instance

            result = run(
                flow._discover_devices(
                    {
                        CONF_USERNAME: "test@example.com",
                        CONF_PASSWORD: "password123",
                    }
                )
            )

        assert result["success"] is False
        assert result["error"] == "no_devices"

    def test_discover_devices_invalid_auth(self):
        """Test discovery with invalid credentials."""
        flow = make_flow()

        with patch(
            "custom_components.iqua_softener.config_flow.IquaSoftener"
        ) as mock_iqua_class:
            mock_iqua_instance = MagicMock()
            mock_iqua_instance.get_devices.side_effect = IquaSoftenerException(
                "Authentication error"
            )
            mock_iqua_class.return_value = mock_iqua_instance

            result = run(
                flow._discover_devices(
                    {
                        CONF_USERNAME: "test@example.com",
                        CONF_PASSWORD: "password123",
                    }
                )
            )

        assert result["success"] is False
        assert result["error"] == "invalid_auth"

    def test_discover_devices_cannot_connect(self):
        """Test discovery with connection failure."""
        flow = make_flow()

        with patch(
            "custom_components.iqua_softener.config_flow.IquaSoftener"
        ) as mock_iqua_class:
            mock_iqua_instance = MagicMock()
            mock_iqua_instance.get_devices.side_effect = IquaSoftenerException(
                "Connection failed"
            )
            mock_iqua_class.return_value = mock_iqua_instance

            result = run(
                flow._discover_devices(
                    {
                        CONF_USERNAME: "test@example.com",
                        CONF_PASSWORD: "password123",
                    }
                )
            )

        assert result["success"] is False
        assert result["error"] == "cannot_connect"

    def test_reconfigure_flow_invalid_entry(self):
        """Test reconfiguration flow with invalid entry."""
        flow = make_flow()
        flow.context = {"entry_id": "invalid_entry_id"}

        result = run(
            flow.async_step_reconfigure(
                {
                    CONF_USERNAME: "test@example.com",
                    CONF_PASSWORD: "password123",
                }
            )
        )

        assert result.get("type") == FlowResultType.FORM
        errors = result.get("errors")
        assert errors is not None and errors.get("base") == "invalid_entry"

    def test_reconfigure_flow_discovers_then_updates_entry(self):
        """Test reconfiguration updates credentials and selected device."""
        entry = SimpleNamespace(
            entry_id="test_entry_id",
            data={
                CONF_USERNAME: "old@example.com",
                CONF_PASSWORD: "old-password",
                CONF_DEVICE_SERIAL_NUMBER: "OLDDEVICE",
            },
        )

        flow = make_flow(entry)
        flow.context = {"entry_id": entry.entry_id}

        with patch.object(flow, "_discover_devices") as mock_discover:
            mock_discover.return_value = {
                "success": True,
                "devices": {"device-id-1": DEVICE},
                "error": None,
            }

            result = run(
                flow.async_step_reconfigure(
                    {
                        CONF_USERNAME: "new@example.com",
                        CONF_PASSWORD: "new-password",
                        CONF_UPDATE_INTERVAL: 15,
                        CONF_ENABLE_WEBSOCKET: True,
                    }
                )
            )

        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == "device"

        def update_entry(config_entry, *, data, unique_id):
            config_entry.data = data
            config_entry.unique_id = unique_id
            return {"type": FlowResultType.ABORT}

        with patch.object(
            flow,
            "async_update_reload_and_abort",
            side_effect=update_entry,
        ) as mock_update:
            result = run(
                flow.async_step_device(
                    {config_flow.CONF_SELECTED_DEVICE: "device-id-1"}
                )
            )

        assert result.get("type") == FlowResultType.ABORT
        assert entry.data[CONF_USERNAME] == "new@example.com"
        assert entry.data[CONF_DEVICE_SERIAL_NUMBER] == "DEVICE123"
        assert entry.data[CONF_PRODUCT_SERIAL_NUMBER] == "PRODUCT456"
        assert entry.unique_id == "DEVICE123"
        mock_update.assert_called_once()
