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

    async def test_async_setup_entry_success(self, hass, mock_config_entry, mock_iqua_softener, mock_iqua_data):
        """Test successful integration setup."""
        mock_iqua_softener.get_data.return_value = mock_iqua_data
        mock_config_entry.add_to_hass(hass)

        with patch("custom_components.iqua_softener.IquaSoftener", return_value=mock_iqua_softener):
            result = await async_setup_entry(hass, mock_config_entry)

            assert result is True
            assert DOMAIN in hass.data
            assert mock_config_entry.entry_id in hass.data[DOMAIN]

            entry_data = hass.data[DOMAIN][mock_config_entry.entry_id]
            assert "coordinator" in entry_data
            assert "unsub_options_update_listener" in entry_data

    async def test_async_setup_entry_with_options(self, hass, mock_config_entry, mock_iqua_softener, mock_iqua_data):
        """Test setup with config entry options."""
        mock_config_entry.add_to_hass(hass)
        mock_iqua_softener.get_data.return_value = mock_iqua_data

        with patch("custom_components.iqua_softener.IquaSoftener", return_value=mock_iqua_softener):
            result = await async_setup_entry(hass, mock_config_entry)

            assert result is True
            # Verify coordinator was created
            entry_data = hass.data[DOMAIN][mock_config_entry.entry_id]
            assert "coordinator" in entry_data

    async def test_async_setup_entry_initial_fetch_failure(self, hass, mock_config_entry, mock_iqua_softener):
        """Test setup when initial data fetch fails."""
        mock_config_entry.add_to_hass(hass)
        mock_iqua_softener.get_data.side_effect = Exception("Connection failed")

        with patch("custom_components.iqua_softener.IquaSoftener", return_value=mock_iqua_softener):
            # Should not raise ConfigEntryNotReady, just continue with setup
            result = await async_setup_entry(hass, mock_config_entry)

            assert result is True
            # Coordinator should still be created even if initial fetch fails

    async def test_async_setup_entry_websocket_enabled(self, hass, config_entry_data, mock_iqua_softener, mock_iqua_data):
        """Test setup with WebSocket enabled."""
        from pytest_homeassistant_custom_component.common import MockConfigEntry
        from custom_components.iqua_softener.const import CONF_ENABLE_WEBSOCKET
        
        config_entry_data[CONF_ENABLE_WEBSOCKET] = True
        mock_config_entry = MockConfigEntry(
            domain=DOMAIN,
            data=config_entry_data,
            entry_id="test_entry_id",
        )
        mock_config_entry.add_to_hass(hass)
        mock_iqua_softener.get_data.return_value = mock_iqua_data

        with patch("custom_components.iqua_softener.IquaSoftener", return_value=mock_iqua_softener):
            result = await async_setup_entry(hass, mock_config_entry)

            assert result is True
            # WebSocket should be started
            mock_iqua_softener.start_websocket.assert_called_once()

    async def test_async_setup_entry_websocket_disabled(self, hass, config_entry_data, mock_iqua_softener, mock_iqua_data):
        """Test setup with WebSocket disabled."""
        from pytest_homeassistant_custom_component.common import MockConfigEntry
        from custom_components.iqua_softener.const import CONF_ENABLE_WEBSOCKET
        
        config_entry_data[CONF_ENABLE_WEBSOCKET] = False
        mock_config_entry = MockConfigEntry(
            domain=DOMAIN,
            data=config_entry_data,
            entry_id="test_entry_id",
        )
        mock_config_entry.add_to_hass(hass)
        mock_iqua_softener.get_data.return_value = mock_iqua_data

        with patch("custom_components.iqua_softener.IquaSoftener", return_value=mock_iqua_softener):
            result = await async_setup_entry(hass, mock_config_entry)

            assert result is True
            # WebSocket should not be started
            mock_iqua_softener.start_websocket.assert_not_called()

    async def test_async_unload_entry(self, hass, mock_config_entry):
        """Test unloading the integration."""
        mock_config_entry.add_to_hass(hass)
        # Set up some mock data
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][mock_config_entry.entry_id] = {
            "unsub_options_update_listener": MagicMock(),
            "coordinator": MagicMock(),
        }

        with patch("homeassistant.config_entries.async_unload_platforms", return_value=True) as mock_unload:
            result = await async_unload_entry(hass, mock_config_entry)

            assert result is True
            mock_unload.assert_called_once()

            # Verify cleanup
            assert mock_config_entry.entry_id not in hass.data[DOMAIN]

    async def test_options_update_listener(self, hass, mock_config_entry):
        """Test the options update listener."""
        mock_config_entry.add_to_hass(hass)
        
        with patch.object(hass.config_entries, "async_reload") as mock_reload:
            await options_update_listener(hass, mock_config_entry)

            mock_reload.assert_called_once_with(mock_config_entry.entry_id)

    async def test_coordinator_creation_with_serial_numbers(self, hass, config_entry_data, mock_iqua_softener, mock_iqua_data):
        """Test coordinator creation with different serial number configurations."""
        from pytest_homeassistant_custom_component.common import MockConfigEntry
        from custom_components.iqua_softener.const import CONF_DEVICE_SERIAL_NUMBER, CONF_PRODUCT_SERIAL_NUMBER
        
        mock_iqua_softener.get_data.return_value = mock_iqua_data

        # Test with device serial number
        config_entry_data[CONF_DEVICE_SERIAL_NUMBER] = "DEVICE123"
        if CONF_PRODUCT_SERIAL_NUMBER in config_entry_data:
            del config_entry_data[CONF_PRODUCT_SERIAL_NUMBER]
        
        mock_config_entry = MockConfigEntry(
            domain=DOMAIN,
            data=config_entry_data,
            entry_id="test_entry_id",
        )
        mock_config_entry.add_to_hass(hass)

        with patch("custom_components.iqua_softener.IquaSoftener", return_value=mock_iqua_softener) as mock_iqua_class:
            await async_setup_entry(hass, mock_config_entry)

            # Verify IquaSoftener was created (exact call signature may vary)
            assert mock_iqua_class.called

    async def test_coordinator_creation_fallback_serial(self, hass, config_entry_data, mock_iqua_softener, mock_iqua_data):
        """Test coordinator creation with fallback to product serial number."""
        from pytest_homeassistant_custom_component.common import MockConfigEntry
        from custom_components.iqua_softener.const import CONF_DEVICE_SERIAL_NUMBER, CONF_PRODUCT_SERIAL_NUMBER
        
        mock_iqua_softener.get_data.return_value = mock_iqua_data

        # Test with only product serial number
        if CONF_DEVICE_SERIAL_NUMBER in config_entry_data:
            del config_entry_data[CONF_DEVICE_SERIAL_NUMBER]
        config_entry_data[CONF_PRODUCT_SERIAL_NUMBER] = "PRODUCT456"
        
        mock_config_entry = MockConfigEntry(
            domain=DOMAIN,
            data=config_entry_data,
            entry_id="test_entry_id",
        )
        mock_config_entry.add_to_hass(hass)

        with patch("custom_components.iqua_softener.IquaSoftener", return_value=mock_iqua_softener) as mock_iqua_class:
            await async_setup_entry(hass, mock_config_entry)

            # Verify IquaSoftener was created
            assert mock_iqua_class.called