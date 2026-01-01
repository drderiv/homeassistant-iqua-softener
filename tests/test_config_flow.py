"""Test the iQua Softener config flow."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
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
)
from custom_components.iqua_softener.vendor.iqua_softener import IquaSoftenerException


class TestIquaSoftenerConfigFlow:
    """Test the iQua Softener config flow."""

    async def test_user_flow_success_device_sn(self, hass):
        """Test successful user flow with device serial number."""
        flow = config_flow.IquaSoftenerConfigFlow()
        flow.hass = hass

        # Mock successful validation
        with patch.object(flow, "_validate_input") as mock_validate:
            mock_validate.return_value = {"success": True, "error": None}

            result = await flow.async_step_user({
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "password123",
                CONF_DEVICE_SERIAL_NUMBER: "DEVICE123",
                CONF_UPDATE_INTERVAL: 10,
                CONF_ENABLE_WEBSOCKET: False,
            })

            assert result.get("type") == FlowResultType.CREATE_ENTRY
            assert result.get("title") == "iQua Device DEVICE123"
            assert result.get("data", {}).get(CONF_USERNAME) == "test@example.com"
            assert result.get("data", {}).get(CONF_DEVICE_SERIAL_NUMBER) == "DEVICE123"

    async def test_user_flow_success_product_sn(self, hass):
        """Test successful user flow with product serial number."""
        flow = config_flow.IquaSoftenerConfigFlow()
        flow.hass = hass

        with patch.object(flow, "_validate_input") as mock_validate:
            mock_validate.return_value = {"success": True, "error": None}

            result = await flow.async_step_user({
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "password123",
                CONF_PRODUCT_SERIAL_NUMBER: "PRODUCT456",
            })

            assert result.get("type") == FlowResultType.CREATE_ENTRY
            assert result.get("title") == "iQua Product PRODUCT456"

    async def test_user_flow_missing_serial_numbers(self, hass):
        """Test user flow with missing serial numbers."""
        flow = config_flow.IquaSoftenerConfigFlow()
        flow.hass = hass

        result = await flow.async_step_user({
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password123",
        })

        assert result.get("type") == FlowResultType.FORM
        errors = result.get("errors")
        assert errors is not None and errors.get("base") == "missing_serial_number"

    async def test_user_flow_validation_failure(self, hass):
        """Test user flow with validation failure."""
        flow = config_flow.IquaSoftenerConfigFlow()
        flow.hass = hass

        with patch.object(flow, "_validate_input") as mock_validate:
            mock_validate.return_value = {"success": False, "error": "invalid_credentials"}

            result = await flow.async_step_user({
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "wrongpassword",
                CONF_DEVICE_SERIAL_NUMBER: "DEVICE123",
            })

            assert result.get("type") == FlowResultType.FORM
            errors = result.get("errors")
            assert errors is not None and errors.get("base") == "invalid_credentials"

    async def test_validate_input_success(self, hass):
        """Test successful input validation."""
        flow = config_flow.IquaSoftenerConfigFlow()
        flow.hass = hass

        mock_data = MagicMock()
        mock_data.state.value = "NORMAL"

        with patch("custom_components.iqua_softener.config_flow.IquaSoftener") as mock_iqua_class:
            mock_iqua_instance = MagicMock()
            mock_iqua_instance.get_data = AsyncMock(return_value=mock_data)
            mock_iqua_class.return_value = mock_iqua_instance

            result = await flow._validate_input({
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "password123",
                CONF_DEVICE_SERIAL_NUMBER: "DEVICE123",
            })

            assert result["success"] is True
            assert result["error"] is None

    async def test_validate_input_device_not_found(self, hass):
        """Test validation with device not found."""
        flow = config_flow.IquaSoftenerConfigFlow()
        flow.hass = hass

        with patch("custom_components.iqua_softener.config_flow.IquaSoftener") as mock_iqua_class:
            mock_iqua_instance = MagicMock()
            mock_iqua_instance.get_data = MagicMock(side_effect=IquaSoftenerException("Device not found"))
            mock_iqua_class.return_value = mock_iqua_instance

            result = await flow._validate_input({
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "password123",
                CONF_DEVICE_SERIAL_NUMBER: "INVALID",
            })

            assert result["success"] is False
            assert result["error"] == "device_not_found"

    async def test_validate_input_cannot_connect(self, hass):
        """Test validation with connection failure."""
        flow = config_flow.IquaSoftenerConfigFlow()
        flow.hass = hass

        with patch("custom_components.iqua_softener.config_flow.IquaSoftener") as mock_iqua_class:
            mock_iqua_instance = MagicMock()
            # Use IquaSoftenerException for connection errors to get proper error code
            from custom_components.iqua_softener.vendor.iqua_softener import IquaSoftenerException
            mock_iqua_instance.get_data = MagicMock(side_effect=IquaSoftenerException("Connection failed"))
            mock_iqua_class.return_value = mock_iqua_instance

            result = await flow._validate_input({
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "password123",
                CONF_DEVICE_SERIAL_NUMBER: "DEVICE123",
            })

            assert result["success"] is False
            assert result["error"] == "cannot_connect"

    async def test_reconfigure_flow_success(self, hass, mock_config_entry, mock_iqua_data):
        """Test successful reconfiguration flow."""
        mock_config_entry.add_to_hass(hass)
        
        with patch("custom_components.iqua_softener.config_flow.IquaSoftener") as mock_iqua_class:
            mock_iqua_instance = MagicMock()
            mock_iqua_instance.get_data = MagicMock(return_value=mock_iqua_data)
            mock_iqua_class.return_value = mock_iqua_instance

            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": "reconfigure", "entry_id": mock_config_entry.entry_id},
                data={
                    CONF_USERNAME: "new@example.com",
                    CONF_PASSWORD: "newpassword",
                    CONF_DEVICE_SERIAL_NUMBER: "NEWDEVICE",
                },
            )

            assert result.get("type") == FlowResultType.ABORT or result.get("type") == FlowResultType.CREATE_ENTRY

    async def test_reconfigure_flow_invalid_entry(self, hass):
        """Test reconfiguration flow with invalid entry."""
        flow = config_flow.IquaSoftenerConfigFlow()
        flow.hass = hass
        flow.context = {"entry_id": "invalid_entry_id"}

        with patch.object(hass.config_entries, "async_get_entry", return_value=None):
            result = await flow.async_step_reconfigure({
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "password123",
            })

            assert result.get("type") == FlowResultType.FORM
            errors = result.get("errors")
            assert errors is not None and errors.get("base") == "invalid_entry"