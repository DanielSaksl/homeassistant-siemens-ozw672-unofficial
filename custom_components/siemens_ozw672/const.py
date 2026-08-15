"""Constants for the Siemens OZW672 integration."""

NAME = "Siemens OZW672"
DOMAIN = "siemens_ozw672"
VERSION = "0.4.0"
ATTRIBUTION = "Integration created by John"

ICON = "mdi:bookmark"
ICON_THERMOMETER = "mdi:thermometer"
ICON_PERCENT = "mdi:percent"
ICON_SWITCH = "mdi:toggle-switch"
ICON_SELECT = "mdi:gesture-tap"
ICON_NUMERIC = "mdi:numeric"
ICON_POWER = "mdi:lightning-bolt"
BINARY_SENSOR_DEVICE_CLASS = "power"

BINARY_SENSOR = "binary_sensor"
SENSOR = "sensor"
SWITCH = "switch"
SELECT = "select"
NUMBER = "number"
PLATFORMS = [SWITCH, SELECT, NUMBER, BINARY_SENSOR, SENSOR]

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_HOST = "hostname"
CONF_PROTOCOL = "protocol"
CONF_DATAPOINTS = "datapoints"
CONF_PREFIX_FUNCTION = "prefix_with_function"
CONF_PREFIX_OPLINE = "prefix_with_opline"
CONF_SCANINTERVAL = "scaninterval"
CONF_HTTPTIMEOUT = "httptimeout"
CONF_HTTPRETRIES = "httpretries"

DEFAULT_HTTPTIMEOUT = 30
DEFAULT_HTTPRETRIES = 2
DEFAULT_SCANINTERVAL = 60
DEFAULT_NAME = DOMAIN
