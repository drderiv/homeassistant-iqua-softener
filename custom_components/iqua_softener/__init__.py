import logging

from homeassistant import config_entries, core
from homeassistant.exceptions import ConfigEntryNotReady
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
    API_URLS,
)
from .sensor import IquaSoftenerCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    hass.data.setdefault(DOMAIN, {})
    hass_data = dict(entry.data)
    if entry.options:
        hass_data.update(entry.options)

    _LOGGER.info("Configuration data: %s", hass_data)
    _LOGGER.info("Entry data: %s", entry.data)
    _LOGGER.info("Entry options: %s", entry.options)

    # Create shared coordinator
    update_interval_minutes = hass_data.get(
        CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
    )
    # Ensure update_interval is an integer (in minutes) and convert to seconds for timedelta
    update_interval_minutes = int(update_interval_minutes) if update_interval_minutes else DEFAULT_UPDATE_INTERVAL
    update_interval_seconds = update_interval_minutes * 60
    enable_websocket = hass_data.get(CONF_ENABLE_WEBSOCKET, DEFAULT_ENABLE_WEBSOCKET)
    _LOGGER.info(
        "Creating coordinator with update interval: %d minutes (%d seconds), WebSocket: %s",
        update_interval_minutes,
        update_interval_seconds,
        enable_websocket,
    )
    # Extract serial numbers from config
    device_sn = hass_data.get(CONF_DEVICE_SERIAL_NUMBER)
    product_sn = hass_data.get(CONF_PRODUCT_SERIAL_NUMBER)
    
    # Get selected API type and corresponding URL
    # Backward compatibility: If api_type is not in config (existing installations),
    # default to legacy iQua API to maintain compatibility with existing setups
    api_type = hass_data.get(CONF_API_TYPE, DEFAULT_API_TYPE)
    api_url = API_URLS.get(api_type, API_URLS[DEFAULT_API_TYPE])
    
    _LOGGER.info("Creating IquaSoftener with device_sn=%s, product_sn=%s, api_type=%s, api_url=%s", 
                 device_sn, product_sn, api_type, api_url)
    
    # Create coordinator (authentication already validated in config flow)
    coordinator = IquaSoftenerCoordinator(
        hass,
        IquaSoftener(
            hass_data[CONF_USERNAME],
            hass_data[CONF_PASSWORD],
            device_serial_number=device_sn,
            product_serial_number=product_sn,
            api_base_url=api_url,
            enable_websocket=enable_websocket,  # Let the library handle WebSocket
        ),
        update_interval_seconds,
        enable_websocket,
        hass_data,  # Pass config data for URL configuration
    )

    # Perform initial data fetch for immediate availability
    try:
        _LOGGER.info("Performing initial data fetch...")
        await coordinator.async_config_entry_first_refresh()
        
        if coordinator.data is None:
            _LOGGER.warning("Initial data fetch returned no data, but continuing setup")
        else:
            _LOGGER.info("Initial data fetch successful")
            
    except Exception as err:
        _LOGGER.warning("Initial data fetch failed, but continuing setup: %s", err)
        # Don't fail the entire setup if initial fetch fails - the coordinator will retry

    unsub_options_update_listener = entry.add_update_listener(options_update_listener)
    hass_data["unsub_options_update_listener"] = unsub_options_update_listener
    hass_data["coordinator"] = coordinator
    hass.data[DOMAIN][entry.entry_id] = hass_data

    # WebSocket will be started automatically by coordinator after first successful data fetch
    # This prevents duplicate WebSocket connections and ensures proper initialization order
    if enable_websocket:
        _LOGGER.info("WebSocket is enabled - will start automatically after first data fetch")
    else:
        _LOGGER.info("WebSocket is disabled in configuration")

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "switch", "select", "button"])
    return True


async def options_update_listener(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
):
    _LOGGER.info("Options updated, reloading integration")
    # Stop WebSocket before reload
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    await coordinator.async_stop_websocket()

    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry with proper cleanup.
    
    Performs graceful shutdown:
    - Stops WebSocket connection if active
    - Cancels pending coordinator tasks
    - Removes options update listener
    - Unloads all platforms
    - Cleans up stored data
    """
    entry_data = hass.data[DOMAIN].get(entry.entry_id)
    
    if entry_data:
        # Stop the WebSocket connection
        coordinator = entry_data.get("coordinator")
        if coordinator:
            try:
                await coordinator.async_stop_websocket()
            except Exception as err:
                _LOGGER.warning("Error stopping WebSocket: %s", err)
        
        # Remove options update listener
        unsub_listener = entry_data.get("unsub_options_update_listener")
        if unsub_listener:
            unsub_listener()

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, ["sensor", "switch", "select", "button"]
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload_ok
