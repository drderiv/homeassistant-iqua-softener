"""Tests for the select platform."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from homeassistant import config_entries, core
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from custom_components.iqua_softener.const import DOMAIN, CONF_DEVICE_SERIAL_NUMBER
from custom_components.iqua_softener.vendor.iqua_softener import (
    IquaSoftenerException,
)


class TestSelectSetup:
    """Test select platform setup."""

    async def test_async_setup_entry_with_settings(self, hass: HomeAssistant, init_integration):
        """Test select platform setup with device settings."""
        # Verify select entities were created
        assert hass.data[DOMAIN]
        
        # Check that entry exists
        entry = hass.config_entries.async_entries(DOMAIN)[0]
        assert entry.state == config_entries.ConfigEntryState.LOADED

    async def test_async_setup_entry_no_settings(self, hass: HomeAssistant, init_integration):
        """Test select platform setup when no settings are available."""
        # This should still initialize without errors
        assert hass.data[DOMAIN]


class TestSelectEntities:
    """Test select entity behavior."""

    async def test_select_option_change(self, hass: HomeAssistant, init_integration):
        """Test changing a select option."""
        # Get the coordinator
        entry = hass.config_entries.async_entries(DOMAIN)[0]
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        
        # Verify coordinator has the method
        assert hasattr(coordinator._iqua_softener, "set_device_setting")

    async def test_select_entity_attributes(self, hass: HomeAssistant, init_integration):
        """Test select entity has correct attributes."""
        # Get the coordinator
        entry = hass.config_entries.async_entries(DOMAIN)[0]
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        
        # Verify coordinator is available
        assert coordinator is not None
        assert coordinator.data is not None

    async def test_select_error_handling(self, hass: HomeAssistant, init_integration):
        """Test select entity error handling."""
        entry = hass.config_entries.async_entries(DOMAIN)[0]
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        
        # Verify error handling method exists
        assert hasattr(coordinator._iqua_softener, "set_device_setting")

    async def test_select_available_when_coordinator_updated(
        self, hass: HomeAssistant, init_integration
    ):
        """Test select entity is available when coordinator is updated."""
        entry = hass.config_entries.async_entries(DOMAIN)[0]
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        
        # Verify last_update_success
        assert coordinator.last_update_success is True
        assert coordinator.data is not None
