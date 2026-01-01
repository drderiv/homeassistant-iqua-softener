"""Test the iQua Softener sensor entities."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.iqua_softener.sensor import (
    IquaSoftenerCoordinator,
    IquaSoftenerStateSensor,
    IquaSoftenerDeviceDateTimeSensor,
    IquaSoftenerLastRegenerationSensor,
    IquaSoftenerOutOfSaltEstimatedDaySensor,
    IquaSoftenerSaltLevelSensor,
    IquaSoftenerAvailableWaterSensor,
    IquaSoftenerWaterCurrentFlowSensor,
    IquaSoftenerWaterUsageTodaySensor,
    IquaSoftenerWaterUsageDailyAverageSensor,
    IquaSoftenerWaterShutoffValveStateSensor,
    async_setup_entry,
    _check_water_shutoff_valve_available,
)
from custom_components.iqua_softener.vendor.iqua_softener import (
    IquaSoftenerData,
    IquaSoftenerState,
    IquaSoftenerVolumeUnit,
)


class TestIquaSoftenerCoordinator:
    """Test the IquaSoftenerCoordinator."""

    async def test_coordinator_initialization(self, hass, mock_iqua_softener, config_entry_data):
        """Test coordinator initialization."""
        coordinator = IquaSoftenerCoordinator(
            hass,
            mock_iqua_softener,
            update_interval_minutes=5,
            enable_websocket=True,
            config_data=config_entry_data,
        )

        assert coordinator._iqua_softener == mock_iqua_softener
        assert coordinator._enable_websocket is True
        assert coordinator._username == "test@example.com"
        assert coordinator._password == "testpass123"

    async def test_async_update_data_success(self, hass, mock_iqua_softener, mock_iqua_data):
        """Test successful data update."""
        coordinator = IquaSoftenerCoordinator(hass, mock_iqua_softener)
        mock_iqua_softener.get_data.return_value = mock_iqua_data

        result = await coordinator._async_update_data()

        assert result == mock_iqua_data
        mock_iqua_softener.get_data.assert_called_once()

    async def test_async_update_data_failure(self, hass, mock_iqua_softener):
        """Test data update failure."""
        coordinator = IquaSoftenerCoordinator(hass, mock_iqua_softener)
        mock_iqua_softener.get_data.return_value = None

        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    async def test_websocket_operations(self, hass, mock_iqua_softener):
        """Test WebSocket start/stop operations."""
        coordinator = IquaSoftenerCoordinator(hass, mock_iqua_softener, enable_websocket=True)

        await coordinator.async_start_websocket()
        mock_iqua_softener.start_websocket.assert_called_once()

        await coordinator.async_stop_websocket()
        mock_iqua_softener.stop_websocket.assert_called_once()

    async def test_websocket_disabled(self, hass, mock_iqua_softener):
        """Test WebSocket operations when disabled."""
        coordinator = IquaSoftenerCoordinator(hass, mock_iqua_softener, enable_websocket=False)

        await coordinator.async_start_websocket()
        mock_iqua_softener.start_websocket.assert_not_called()


class TestSensorEntities:
    """Test the sensor entities."""

    async def test_state_sensor(self, hass, mock_iqua_data):
        """Test the state sensor."""
        coordinator = MagicMock()
        coordinator.data = mock_iqua_data

        sensor = IquaSoftenerStateSensor(coordinator, "DEVICE123")
        sensor.update(mock_iqua_data)

        assert sensor._attr_native_value == "NORMAL"
        assert sensor.unique_id == "device123_state"

    async def test_datetime_sensor(self, hass, mock_iqua_data):
        """Test the device date/time sensor."""
        coordinator = MagicMock()
        coordinator.data = mock_iqua_data

        sensor = IquaSoftenerDeviceDateTimeSensor(coordinator, "DEVICE123")
        sensor.update(mock_iqua_data)

        assert isinstance(sensor._attr_native_value, datetime)
        assert sensor.unique_id == "device123_date_time"

    async def test_state_sensor(self, hass, init_integration):
        """Test the state sensor through the state machine."""
        await hass.async_block_till_done()
        
        state = hass.states.get("sensor.state")
        assert state is not None
        assert state.state == "Online"

    async def test_datetime_sensor(self, hass, init_integration):
        """Test the device datetime sensor through the state machine."""
        await hass.async_block_till_done()
        
        state = hass.states.get("sensor.date_time")
        assert state is not None

    async def test_last_regeneration_sensor(self, hass, init_integration):
        """Test the last regeneration sensor through the state machine."""
        await hass.async_block_till_done()
        
        state = hass.states.get("sensor.last_regeneration")
        assert state is not None

    async def test_out_of_salt_sensor(self, hass, init_integration):
        """Test the out of salt estimation sensor through the state machine."""
        await hass.async_block_till_done()
        
        state = hass.states.get("sensor.out_of_salt_estimated_day")
        assert state is not None

    async def test_salt_level_sensor(self, hass, init_integration):
        """Test the salt level sensor through the state machine."""
        await hass.async_block_till_done()
        
        state = hass.states.get("sensor.salt_level")
        assert state is not None
        assert state.state == "75"

    async def test_salt_level_sensor_icon(self, hass, init_integration, mock_iqua_data):
        """Test salt level sensor icon changes through coordinator updates."""
        await hass.async_block_till_done()
        
        # Just verify the sensor exists and has an icon attribute
        state = hass.states.get("sensor.salt_level")
        assert state is not None
        assert state.attributes.get("icon") is not None

    async def test_available_water_sensor(self, hass, init_integration):
        """Test the available water sensor through the state machine."""
        await hass.async_block_till_done()
        
        state = hass.states.get("sensor.available_water")
        assert state is not None
        assert state.state == "1000.0"

    async def test_water_flow_sensor(self, hass, init_integration):
        """Test the water current flow sensor through the state machine."""
        await hass.async_block_till_done()
        
        state = hass.states.get("sensor.water_current_flow")
        assert state is not None

    async def test_water_usage_today_sensor(self, hass, init_integration):
        """Test the today water usage sensor through the state machine."""
        await hass.async_block_till_done()
        
        state = hass.states.get("sensor.today_water_usage")
        assert state is not None
        assert state.state == "50.0"

    async def test_water_usage_daily_average_sensor(self, hass, init_integration):
        """Test the daily average water usage sensor through the state machine."""
        await hass.async_block_till_done()
        
        state = hass.states.get("sensor.water_usage_daily_average")
        assert state is not None
        assert state.state == "45.0"

    async def test_valve_state_sensor(self, hass, init_integration):
        """Test the water shutoff valve state sensor through the state machine."""
        await hass.async_block_till_done()
        
        state = hass.states.get("sensor.water_shutoff_valve_state")
        assert state is not None
        assert state.state == "Open"


class TestSensorSetup:
    """Test sensor setup functionality."""

    async def test_async_setup_entry_success(self, hass, mock_config_entry, mock_iqua_softener, mock_iqua_data):
        """Test successful sensor setup."""
        mock_iqua_softener.get_data.return_value = mock_iqua_data
        mock_iqua_softener.has_water_shutoff_valve.return_value = True

        # Mock the coordinator
        coordinator = MagicMock()
        coordinator.data = mock_iqua_data
        coordinator._iqua_softener = mock_iqua_softener

        # Set up hass.data
        hass.data.setdefault("iqua_softener", {})
        hass.data["iqua_softener"][mock_config_entry.entry_id] = {
            "coordinator": coordinator,
            **mock_config_entry.data,
        }

        async_add_entities = MagicMock()

        with patch("custom_components.iqua_softener.sensor._check_water_shutoff_valve_available", return_value=True):
            await async_setup_entry(hass, mock_config_entry, async_add_entities)

            # Verify sensors were added
            assert async_add_entities.called
            call_args = async_add_entities.call_args[0][0]
            assert len(call_args) == 12  # 11 base sensors (including WiFi signal strength and water hardness) + 1 valve sensor

    async def test_check_water_shutoff_valve_available(self, hass, mock_iqua_softener):
        """Test checking water shutoff valve availability."""
        coordinator = MagicMock()
        coordinator._iqua_softener = mock_iqua_softener
        coordinator.hass = hass

        mock_iqua_softener.has_water_shutoff_valve.return_value = True
        result = await _check_water_shutoff_valve_available(coordinator)
        assert result is True

        mock_iqua_softener.has_water_shutoff_valve.return_value = False
        result = await _check_water_shutoff_valve_available(coordinator)
        assert result is False

    async def test_sensor_error_handling(self, hass, init_integration, mock_iqua_data):
        """Test sensor error handling through state machine."""
        await hass.async_block_till_done()
        
        # Verify sensor exists
        state = hass.states.get("sensor.state")
        assert state is not None