"""Test diagnostics support for iQua Softener integration."""
from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant

from custom_components.iqua_softener.diagnostics import async_get_config_entry_diagnostics


class TestDiagnostics:
    """Test diagnostics functionality."""

    async def test_diagnostics_basic(self, hass: HomeAssistant, init_integration):
        """Test basic diagnostics output."""
        config_entry = init_integration
        
        diag_data = await async_get_config_entry_diagnostics(hass, config_entry)
        
        # Verify structure
        assert "entry" in diag_data
        assert "configuration" in diag_data
        assert "coordinator" in diag_data
        assert "device" in diag_data
        assert "connection" in diag_data
        assert "platforms" in diag_data
    
    async def test_diagnostics_entry_info(self, hass: HomeAssistant, init_integration):
        """Test entry information in diagnostics."""
        config_entry = init_integration
        
        diag_data = await async_get_config_entry_diagnostics(hass, config_entry)
        
        entry_info = diag_data["entry"]
        assert entry_info["title"] == config_entry.title
        assert entry_info["version"] == config_entry.version
        assert entry_info["source"] == config_entry.source
        assert "state" in entry_info
    
    async def test_diagnostics_configuration(self, hass: HomeAssistant, init_integration):
        """Test configuration in diagnostics (without sensitive data)."""
        config_entry = init_integration
        
        diag_data = await async_get_config_entry_diagnostics(hass, config_entry)
        
        config = diag_data["configuration"]
        # Verify username is present (but password is excluded)
        assert "username" in config
        assert "device_serial_number" in config
        assert "update_interval_minutes" in config
        assert "websocket_enabled" in config
    
    async def test_diagnostics_coordinator(self, hass: HomeAssistant, init_integration):
        """Test coordinator information in diagnostics."""
        config_entry = init_integration
        
        diag_data = await async_get_config_entry_diagnostics(hass, config_entry)
        
        coordinator = diag_data["coordinator"]
        assert "last_update_success" in coordinator
        assert coordinator["last_update_success"] is True
        assert "last_exception" in coordinator
        assert "update_interval_seconds" in coordinator
    
    async def test_diagnostics_device_data(self, hass: HomeAssistant, init_integration):
        """Test device data in diagnostics."""
        config_entry = init_integration
        
        diag_data = await async_get_config_entry_diagnostics(hass, config_entry)
        
        device = diag_data["device"]
        assert "state" in device
        assert device["state"] == "Online"  # Note: case-sensitive
        assert "salt_level_percent" in device
        assert "water_usage_today" in device
    
    async def test_diagnostics_connection_status(self, hass: HomeAssistant, init_integration):
        """Test connection status in diagnostics."""
        config_entry = init_integration
        
        diag_data = await async_get_config_entry_diagnostics(hass, config_entry)
        
        connection = diag_data["connection"]
        assert "api_reachable" in connection
        assert connection["api_reachable"] is True
        assert "last_error" in connection
        assert "backoff_failure_count" in connection
        assert connection["backoff_failure_count"] == 0
    
    async def test_diagnostics_platforms(self, hass: HomeAssistant, init_integration):
        """Test platform entity counts in diagnostics."""
        config_entry = init_integration
        
        diag_data = await async_get_config_entry_diagnostics(hass, config_entry)
        
        platforms = diag_data["platforms"]
        assert "sensor_count" in platforms
        assert "switch_count" in platforms
        # At least one sensor and one switch should exist
        assert isinstance(platforms["sensor_count"], int)
        assert isinstance(platforms["switch_count"], int)
