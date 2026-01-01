"""Diagnostics support for iQua Softener integration.

Provides diagnostic data for troubleshooting and support.
Accessible from Settings → Devices & Services → iQua Softener → Options → Diagnostics
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_USERNAME, CONF_DEVICE_SERIAL_NUMBER, CONF_PRODUCT_SERIAL_NUMBER

_LOGGER = logging.getLogger(__name__)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry.
    
    Provides comprehensive diagnostic information for troubleshooting:
    - Configuration summary (without sensitive data)
    - Coordinator state and update intervals
    - Device data status and last values
    - Connection and API status
    - Error history and recovery state
    
    Sensitive data (passwords) is intentionally excluded.
    
    Args:
        hass: Home Assistant instance
        entry: Config entry being diagnosed
        
    Returns:
        Dictionary containing diagnostic data
    """
    entry_data = hass.data[DOMAIN].get(entry.entry_id, {})
    coordinator = entry_data.get("coordinator")
    
    # Build configuration summary (excluding sensitive data)
    config_summary = {
        "username": entry.data.get(CONF_USERNAME),
        "device_serial_number": entry.data.get(CONF_DEVICE_SERIAL_NUMBER),
        "product_serial_number": entry.data.get(CONF_PRODUCT_SERIAL_NUMBER),
        "update_interval_minutes": entry.data.get("update_interval", 10),
        "websocket_enabled": entry.data.get("enable_websocket", False),
    }
    
    # Build coordinator state information
    coordinator_state = {
        "last_update_success": coordinator.last_update_success if coordinator else None,
        "last_exception": (
            coordinator.last_exception.__class__.__name__ 
            if coordinator and coordinator.last_exception 
            else None
        ),
        "update_interval_seconds": (
            coordinator.update_interval.total_seconds() 
            if coordinator and coordinator.update_interval 
            else None
        ),
    }
    
    # Build device data information (if available)
    device_state = {}
    if coordinator and coordinator.data:
        try:
            data = coordinator.data
            device_state = {
                "state": data.state.value if hasattr(data, "state") else "unknown",
                "serial_number": data.serial_number if hasattr(data, "serial_number") else None,
                "model": data.model if hasattr(data, "model") else None,
                "firmware": data.firmware if hasattr(data, "firmware") else None,
                "salt_level_percent": data.salt_level if hasattr(data, "salt_level") else None,
                "water_usage_today": data.water_usage_today if hasattr(data, "water_usage_today") else None,
                "water_usage_daily_average": (
                    data.water_usage_daily_average 
                    if hasattr(data, "water_usage_daily_average") 
                    else None
                ),
                "available_water": data.available_water if hasattr(data, "available_water") else None,
                "water_current_flow": data.water_current_flow if hasattr(data, "water_current_flow") else None,
                "water_shutoff_valve": (
                    data.water_shutoff_valve if hasattr(data, "water_shutoff_valve") else None
                ),
                "last_regeneration": (
                    data.last_regeneration.isoformat() 
                    if hasattr(data, "last_regeneration") and data.last_regeneration 
                    else None
                ),
                "out_of_salt_estimated_day": (
                    data.out_of_salt_estimated_day.isoformat() 
                    if hasattr(data, "out_of_salt_estimated_day") and data.out_of_salt_estimated_day 
                    else None
                ),
            }
        except Exception as err:
            _LOGGER.error("Error collecting device state for diagnostics: %s", err)
            device_state = {"error": str(err)}
    
    # Build API/connection status
    connection_status = {
        "api_reachable": coordinator.last_update_success if coordinator else None,
        "last_error": (
            coordinator.last_exception.__class__.__name__ 
            if coordinator and coordinator.last_exception 
            else None
        ),
        "backoff_failure_count": (
            coordinator._failure_count 
            if coordinator and hasattr(coordinator, "_failure_count") 
            else 0
        ),
    }
    
    # Build platform entities information
    platforms_info = {
        "sensor_count": len(
            [e for e in hass.states.async_entity_ids() 
             if "sensor." in e and "iqua" in e.lower()]
        ),
        "switch_count": len(
            [e for e in hass.states.async_entity_ids() 
             if "switch." in e and "iqua" in e.lower()]
        ),
    }
    
    return {
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "source": entry.source,
            "state": entry.state.value,
        },
        "configuration": config_summary,
        "coordinator": coordinator_state,
        "device": device_state,
        "connection": connection_status,
        "platforms": platforms_info,
    }
