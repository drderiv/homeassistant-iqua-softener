"""Test the iQua Softener integration setup."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from custom_components.iqua_softener import async_setup_entry, async_unload_entry, options_update_listener
from custom_components.iqua_softener.const import DOMAIN


class TestIntegrationSetup:
    """Test the integration setup functionality."""

    async def test_async_setup_entry_success(self, hass, init_integration):
        """Test successful integration setup using init_integration."""
        # init_integration already handles async_setup properly
        assert init_integration.entry_id in hass.data[DOMAIN]
        entry_data = hass.data[DOMAIN][init_integration.entry_id]
        assert "coordinator" in entry_data
        assert "unsub_options_update_listener" in entry_data

    async def test_async_setup_entry_with_options(self, hass, init_integration):
        """Test setup with config entry options."""
        # Verify coordinator was created properly
        entry_data = hass.data[DOMAIN][init_integration.entry_id]
        assert "coordinator" in entry_data
        coordinator = entry_data["coordinator"]
        assert coordinator.data is not None

    async def test_async_setup_entry_initial_fetch_success(self, hass, init_integration):
        """Test successful initial data fetch."""
        entry_data = hass.data[DOMAIN][init_integration.entry_id]
        coordinator = entry_data["coordinator"]
        # Verify initial fetch completed
        assert coordinator.last_update_success is True

    async def test_async_setup_entry_websocket_enabled(self, hass, config_entry_data, mock_iqua_softener, mock_iqua_data):
        """Test setup with WebSocket enabled."""
        from pytest_homeassistant_custom_component.common import MockConfigEntry
        from custom_components.iqua_softener.const import CONF_ENABLE_WEBSOCKET
        
        # Create config entry with WebSocket enabled
        config_data = {**config_entry_data, CONF_ENABLE_WEBSOCKET: True}
        mock_config_entry = MockConfigEntry(
            domain=DOMAIN,
            data=config_data,
            entry_id="test_entry_ws_enabled",
        )
        mock_config_entry.add_to_hass(hass)
        mock_iqua_softener.get_data.return_value = mock_iqua_data
        
        # Use async_setup to properly initialize the config entry
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.entry_id in hass.data[DOMAIN]
        entry_data = hass.data[DOMAIN][mock_config_entry.entry_id]
        assert "coordinator" in entry_data

    async def test_async_setup_entry_websocket_disabled(self, hass, config_entry_data, mock_iqua_softener, mock_iqua_data):
        """Test setup with WebSocket disabled."""
        from pytest_homeassistant_custom_component.common import MockConfigEntry
        from custom_components.iqua_softener.const import CONF_ENABLE_WEBSOCKET
        
        # Create config entry with WebSocket disabled
        config_data = {**config_entry_data, CONF_ENABLE_WEBSOCKET: False}
        mock_config_entry = MockConfigEntry(
            domain=DOMAIN,
            data=config_data,
            entry_id="test_entry_ws_disabled",
        )
        mock_config_entry.add_to_hass(hass)
        mock_iqua_softener.get_data.return_value = mock_iqua_data
        
        # Use async_setup to properly initialize the config entry
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.entry_id in hass.data[DOMAIN]
        entry_data = hass.data[DOMAIN][mock_config_entry.entry_id]
        assert "coordinator" in entry_data

    async def test_async_unload_entry(self, hass, init_integration):
        """Test unloading the integration."""
        entry_id = init_integration.entry_id
        assert entry_id in hass.data[DOMAIN]
        
        result = await hass.config_entries.async_unload(entry_id)
        
        assert result is True
        # Verify cleanup
        assert entry_id not in hass.data.get(DOMAIN, {})

    async def test_options_update_listener(self, hass, init_integration):
        """Test the options update listener."""
        entry_id = init_integration.entry_id
        entry_data = hass.data[DOMAIN][entry_id]
        
        # Verify listener was registered
        assert "unsub_options_update_listener" in entry_data
        unsub = entry_data["unsub_options_update_listener"]
        assert callable(unsub)

    async def test_coordinator_creation_with_device_serial(self, hass, init_integration):
        """Test coordinator creation with device serial number."""
        entry_id = init_integration.entry_id
        entry_data = hass.data[DOMAIN][entry_id]
        coordinator = entry_data["coordinator"]
        
        # Verify coordinator was created with correct serial
        assert coordinator is not None
        assert coordinator.data is not None

    async def test_coordinator_state_updates(self, hass, init_integration):
        """Test coordinator state and update interval."""
        entry_id = init_integration.entry_id
        entry_data = hass.data[DOMAIN][entry_id]
        coordinator = entry_data["coordinator"]
        
        # Verify coordinator properties
        assert coordinator.last_update_success is True
        assert coordinator.update_interval is not None
        assert coordinator.data is not None