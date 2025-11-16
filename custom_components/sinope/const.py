"""Constants for Sinope GT125 component."""

import json
import pathlib

# Base component constants, some loaded directly from the manifest
_LOADER_PATH = pathlib.Path(__loader__.path)
_MANIFEST_PATH = _LOADER_PATH.parent / "manifest.json"
with pathlib.Path.open(_MANIFEST_PATH, encoding="Latin1") as json_file:
    data = json.load(json_file)
NAME = f"{data['name']}"
DOMAIN = f"{data['domain']}"
VERSION = f"{data['version']}"
ISSUE_URL = f"{data['issue_tracker']}"
REQUIRE = "2025.1.1"
DOC_URL = f"{data['documentation']}"

STARTUP_MESSAGE = f"""
-------------------------------------------------------------------
{NAME} ({DOMAIN})
Version: {VERSION}
Requirement: Home Assistant minimum version {REQUIRE}
This is a custom integration!
If you have any issues with this you need to open an issue here: {ISSUE_URL}
Documentation: {DOC_URL}
-------------------------------------------------------------------
"""

CONF_API_KEY_2 = "api_key_2"
CONF_ID_2 = "id_2"
CONF_SERVER = 'server'
CONF_SERVER_2 = 'server_2'
CONF_MY_CITY = 'my_city'

ATTR_OUTSIDE_TEMPERATURE = "temperature"
ATTR_MIN_TEMP = "tempMin"
ATTR_MAX_TEMP = "tempMax"
ATTR_KEYPAD_LOCK = "lock"
ATTR_EVENT_TIMER = "time"
ATTR_DISPLAY = "display"
ATTR_LEVEL = "level"
ATTR_STATE = "state"
ATTR_INTENSITY = "intensity"
ATTR_RED = "red"
ATTR_GREEN = "green"
ATTR_BLUE = "blue"

SERVICE_SET_OUTSIDE_TEMPERATURE = "set_outside_temperature"
SERVICE_SET_CLIMATE_KEYPAD_LOCK = "set_climate_keypad_lock"
SERVICE_SET_LIGHT_KEYPAD_LOCK = "set_light_keypad_lock"
SERVICE_SET_SWITCH_KEYPAD_LOCK = "set_switch_keypad_lock"
SERVICE_SET_LIGHT_EVENT_TIMER = "set_light_event_timer"
SERVICE_SET_SWITCH_EVENT_TIMER = "set_switch_event_timer"
SERVICE_SET_SECOND_DISPLAY = "set_second_display"
SERVICE_SET_BACKLIGHT_IDLE = "set_backlight_idle"
SERVICE_SET_BACKLIGHT_STATE = "set_backlight_state"
SERVICE_SET_LED_INDICATOR = "set_led_indicator"
SERVICE_SET_CLIMATE_BASIC_DATA = "set_climate_basic_data"
SERVICE_SET_LIGHT_BASIC_DATA = "set_light_basic_data"
SERVICE_SET_SWITCH_BASIC_DATA = "set_switch_basic_data"
SERVICE_SET_MAX_SETPOINT = "set_max_setpoint"
SERVICE_SET_MIN_SETPOINT = "set_min_setpoint"

SUPPORT_OUTSIDE_TEMPERATURE = 128
SUPPORT_KEYPAD_LOCK = 256
SUPPORT_EVENT_TIMER = 128
SUPPORT_SECOND_DISPLAY = 512

PRESET_BYPASS = 'temporary'
