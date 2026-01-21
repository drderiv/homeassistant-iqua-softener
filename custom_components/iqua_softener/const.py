from typing import Final

DOMAIN: Final = "iqua_softener"

CONF_USERNAME: Final = "username"
CONF_PASSWORD: Final = "password"
CONF_DEVICE_SERIAL_NUMBER: Final = "device_sn"
CONF_PRODUCT_SERIAL_NUMBER: Final = "product_sn"
CONF_UPDATE_INTERVAL: Final = "update_interval"
CONF_ENABLE_WEBSOCKET: Final = "enable_websocket"
CONF_API_TYPE: Final = "api_type"

DEFAULT_UPDATE_INTERVAL: Final = 5  # minutes
DEFAULT_ENABLE_WEBSOCKET: Final = True
DEFAULT_API_TYPE: Final = "iqua"

# API endpoint URLs
API_TYPE_IQUA: Final = "iqua"
API_TYPE_IQUA2: Final = "iqua2"
API_URL_IQUA: Final = "https://api.myiquaapp.com/v1"
API_URL_IQUA2: Final = "https://api.iqua2.com/v1"

API_URLS: Final = {
    API_TYPE_IQUA: API_URL_IQUA,
    API_TYPE_IQUA2: API_URL_IQUA2,
}

# Switch optimistic state timeout (seconds)
SWITCH_OPTIMISTIC_TIMEOUT: Final = 10

VOLUME_FLOW_RATE_LITERS_PER_MINUTE: Final = "L/m"
VOLUME_FLOW_RATE_GALLONS_PER_MINUTE: Final = "gal/m"
