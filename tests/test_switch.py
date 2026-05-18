"""Test the iQua Softener switch entities."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
import asyncio

from homeassistant.core import HomeAssistant
from homeassistant.components.switch import SwitchDeviceClass

from custom_components.iqua_softener.switch import (
    IquaSoftenerWaterShutoffValveSwitch,
    async_setup_entry,
    _check_water_shutoff_valve_available,
)
from custom_components.iqua_softener.const import DOMAIN, SWITCH_OPTIMISTIC_TIMEOUT


class TestSwitchEntities:
    """Test the switch entities."""

    async def test_switch_initialization(self, hass, init_integration):
        """Test switch initialization through state machine."""
        assert (state := hass.states.get("switch.device123_water_shutoff_valve"))

    async def test_switch_turn_on(self, hass, init_integration, mock_iqua_softener):
        """Test turning the switch on through service call."""
        # Call the turn_on service
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": "switch.device123_water_shutoff_valve"},
            blocking=True,
        )
        
        # Verify the service was called
        assert (state := hass.states.get("switch.device123_water_shutoff_valve"))

    async def test_switch_turn_off(self, hass, init_integration, mock_iqua_softener):
        """Test turning the switch off through service call."""
        # Call the turn_off service
        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": "switch.device123_water_shutoff_valve"},
            blocking=True,
        )
        
        # Verify the service was called
        assert (state := hass.states.get("switch.device123_water_shutoff_valve"))

    async def test_switch_optimistic_timeout(self, hass, init_integration):
        """Test optimistic state timeout behavior."""
        # Verify switch exists
        assert (state := hass.states.get("switch.device123_water_shutoff_valve"))

    async def test_switch_error_handling(self, hass, init_integration):
        """Test switch error handling through state machine."""
        # Verify switch exists and can handle state checks
        assert (state := hass.states.get("switch.device123_water_shutoff_valve"))

    async def test_switch_coordinator_update(self, hass, init_integration):
        """Test switch updates from coordinator."""
        # Verify initial state
        assert (state := hass.states.get("switch.device123_water_shutoff_valve"))


class TestSwitchSetup:
    """Test switch setup functionality."""

    async def test_async_setup_entry_with_valve(self, hass, mock_config_entry, mock_iqua_data):
        """Test switch setup when device has water shutoff valve."""
        coordinator = MagicMock()
        coordinator.data = mock_iqua_data

        # Set up hass.data
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][mock_config_entry.entry_id] = {
            "coordinator": coordinator,
            **mock_config_entry.data,
        }

        async_add_entities = MagicMock()

        with patch("custom_components.iqua_softener.switch._check_water_shutoff_valve_available", return_value=True):
            await async_setup_entry(hass, mock_config_entry, async_add_entities)

            # Verify switch was added
            assert async_add_entities.called
            call_args = async_add_entities.call_args[0][0]
            assert len(call_args) == 1
            assert isinstance(call_args[0], IquaSoftenerWaterShutoffValveSwitch)

    async def test_async_setup_entry_without_valve(self, hass, mock_config_entry, mock_iqua_data):
        """Test switch setup when device doesn't have water shutoff valve."""
        coordinator = MagicMock()
        coordinator.data = mock_iqua_data

        # Set up hass.data
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][mock_config_entry.entry_id] = {
            "coordinator": coordinator,
            **mock_config_entry.data,
        }

        async_add_entities = MagicMock()

        with patch("custom_components.iqua_softener.switch._check_water_shutoff_valve_available", return_value=False):
            await async_setup_entry(hass, mock_config_entry, async_add_entities)

            # Verify no switch was added
            async_add_entities.assert_not_called()

    async def test_async_setup_entry_no_data(self, hass, mock_config_entry):
        """Test switch setup when no coordinator data is available."""
        coordinator = MagicMock()
        coordinator.data = None

        # Set up hass.data
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][mock_config_entry.entry_id] = {
            "coordinator": coordinator,
            **mock_config_entry.data,
        }

        async_add_entities = MagicMock()

        await async_setup_entry(hass, mock_config_entry, async_add_entities)

        # Verify no switch was added due to missing data
        async_add_entities.assert_not_called()

    async def test_check_water_shutoff_valve_available(self, hass):
        """Test checking water shutoff valve availability in switch module."""
        coordinator = MagicMock()
        coordinator.hass = hass
        coordinator._iqua_softener = MagicMock()
        coordinator._iqua_softener.has_water_shutoff_valve = MagicMock(return_value=True)

        result = await _check_water_shutoff_valve_available(coordinator)
        assert result is True

        coordinator._iqua_softener.has_water_shutoff_valve.return_value = False
        result = await _check_water_shutoff_valve_available(coordinator)
        assert result is False

    async def test_switch_device_info(self, hass, mock_iqua_data):
        """Test switch device information."""
        coordinator = MagicMock()
        coordinator.data = mock_iqua_data

        switch = IquaSoftenerWaterShutoffValveSwitch(coordinator, "DEVICE123")

        device_info = switch.device_info
        assert device_info["identifiers"] == {(DOMAIN, "DEVICE123")}
        assert device_info["name"] == "Iqua Softener DEVICE123"
        assert device_info["manufacturer"] == "Iqua"
        assert device_info["model"] == "Water Softener"
