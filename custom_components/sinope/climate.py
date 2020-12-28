"""
Support for Sinope thermostat.
family 10 = thermostat TH1120RF 3000W and 4000W
family 20 = thermostat TH1300RF 3600W floor, TH1500RF double pole thermostat
family 21 = thermostat TH1400RF low voltage
For more details about this platform, please refer to the documentation at
https://www.sinopetech.com/en/support/#api
"""
import asyncio
import json
import logging
import os

import voluptuous as vol
import time

import custom_components.sinope as sinope
from . import (
    SCAN_INTERVAL,
    CONFDIR,
)

from homeassistant.components.climate import (
    ClimateEntity,
    PLATFORM_SCHEMA,
)

from homeassistant.helpers import (
    config_validation as cv,
    discovery,
    entity_platform,
    service,
)

from homeassistant.components.climate.const import (
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    HVAC_MODE_AUTO,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_PRESET_MODE,
    PRESET_AWAY,
    PRESET_NONE,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
)

from homeassistant.const import (
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    ATTR_TEMPERATURE,
    ATTR_ENTITY_ID,
)

from datetime import timedelta
from homeassistant.core import (
    ServiceCall,
    callback,
)

from homeassistant.helpers.event import track_time_interval
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers import (
    entity_platform,
    service,
    entity_component,
    entity_registry,
    device_registry,
)

from .const import (
    DOMAIN,
    ATTR_OUTSIDE_TEMPERATURE,
    ATTR_KEYPAD_LOCK,
    ATTR_DISPLAY,
    ATTR_LEVEL,
    ATTR_STATE,
    SUPPORT_OUTSIDE_TEMPERATURE,
    SUPPORT_KEYPAD_LOCK,
    SUPPORT_SECOND_DISPLAY,
    SERVICE_SET_OUTSIDE_TEMPERATURE,
    SERVICE_SET_KEYPAD_LOCK,
    SERVICE_SET_SECOND_DISPLAY,
    SERVICE_SET_BACKLIGHT_IDLE,
    SERVICE_SET_BACKLIGHT_STATE,
    SERVICE_SET_BASIC_DATA,
    PRESET_BYPASS,
)

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE | SUPPORT_OUTSIDE_TEMPERATURE | SUPPORT_KEYPAD_LOCK | SUPPORT_SECOND_DISPLAY)

DEFAULT_NAME = "sinope"
DATA_DOMAIN = 'data_' + DOMAIN

SINOPE_MODE_OFF = 0
SINOPE_MODE_FREEZE_PROTECT = 1
SINOPE_MODE_MANUAL = 2
SINOPE_MODE_AUTO = 3
SINOPE_MODE_AWAY = 5

SINOPE_BYPASS_FLAG = 128
SINOPE_BYPASSABLE_MODES = [
    SINOPE_MODE_FREEZE_PROTECT,
    SINOPE_MODE_AUTO,
    SINOPE_MODE_AWAY,
]

SINOPE_MODE_AUTO_BYPASS = (SINOPE_MODE_AUTO | SINOPE_BYPASS_FLAG)

SUPPORTED_HVAC_MODES = [
    HVAC_MODE_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
]

PRESET_MODES = [
    PRESET_NONE,
    PRESET_AWAY,
    PRESET_BYPASS,
]

IMPLEMENTED_DEVICE_TYPES = [10, 20, 21]

SET_OUTSIDE_TEMPERATURE_SCHEMA = vol.Schema(
    {
         vol.Required(ATTR_ENTITY_ID): cv.entity_id,
         vol.Required(ATTR_OUTSIDE_TEMPERATURE): vol.All(
             vol.Coerce(float), vol.Range(min=-40, max=40)
         ),
    }
)

SET_KEYPAD_LOCK_SCHEMA = vol.Schema(
    {
         vol.Required(ATTR_ENTITY_ID): cv.entity_id,
         vol.Required(ATTR_KEYPAD_LOCK): cv.string,
    }
)

SET_SECOND_DISPLAY_SCHEMA = vol.Schema(
    {
         vol.Required(ATTR_ENTITY_ID): cv.entity_id,
         vol.Required(ATTR_DISPLAY): cv.string,
    }
)

SET_BACKLIGHT_STATE_SCHEMA = vol.Schema(
    {
         vol.Required(ATTR_ENTITY_ID): cv.entity_id,
         vol.Required(ATTR_STATE): vol.All(
             vol.Coerce(int), vol.Range(min=0, max=3)
         ),
    }
)

SET_BACKLIGHT_IDLE_SCHEMA = vol.Schema(
    {
         vol.Required(ATTR_ENTITY_ID): cv.entity_id,
         vol.Required(ATTR_LEVEL): vol.All(
             vol.Coerce(int), vol.Range(min=0, max=100)
         ),
    }
)

SET_BASIC_DATA_SCHEMA = vol.Schema(
    {
         vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    }
)

def setup_platform(
    hass: HomeAssistantType,
    config_entry,
    add_entities,
    discovery_info = None,
) -> None:
    """Set up the sinope thermostats."""
    data = hass.data[sinope.DATA_DOMAIN]
    CONF_file = CONFDIR + "sinope_devices.json"
    dev_list = []
    with open(CONF_file) as f:
        for line in f:
            dev_list.append(json.loads(line))         
    f.close()
    i = 2
    tot = len(dev_list)
    entities = []
    for a in dev_list:
        x = int(dev_list[i][2])
        if x in IMPLEMENTED_DEVICE_TYPES:
            device_name = "{} {}".format(DEFAULT_NAME, dev_list[i][1])
            device_id = "{}".format(dev_list[i][0])
            device_type = "{}".format(int(dev_list[i][2]))
            server = 1
            entities.append(SinopeThermostat(data, device_id, device_name, device_type, server))
        if i == tot-1:
            break
        i = i + 1

    if os.path.exists(CONFDIR+'sinope_devices_2.json') == True:
        CONF_file_2 = CONFDIR + "sinope_devices_2.json"
        dev_list_2 = []
        with open(CONF_file_2) as g:
            for line in g:
                dev_list_2.append(json.loads(line))         
        g.close()
        i = 2
        tot2 = len(dev_list_2)
        for a in dev_list_2:
            x = int(dev_list_2[i][2])
            if x in IMPLEMENTED_DEVICE_TYPES:
                device_name = "{} {}".format(DEFAULT_NAME, dev_list_2[i][1])
                device_id = "{}".format(dev_list_2[i][0])
                device_type = "{}".format(int(dev_list_2[i][2]))
                server = 2
                entities.append(SinopeThermostat(data, device_id, device_name, device_type, server))
            if i == tot2-1:
                break
            i = i + 1

    add_entities(entities, True)

    def set_outside_temperature_service(service):
        """ send outside temperature to thermostats"""
        entity_id = service.data[ATTR_ENTITY_ID]
        value = {}
        for thermostat in entities:
            if thermostat.entity_id == entity_id:
                value = {"id": thermostat.unique_id, "temperature": service.data[ATTR_OUTSIDE_TEMPERATURE]}
                thermostat.set_outside_temperature(value)
                thermostat.schedule_update_ha_state(True)
                break

    def set_keypad_lock_service(service):
        """ lock/unlock keypad device"""
        entity_id = service.data[ATTR_ENTITY_ID]
        value = {}
        for thermostat in entities:
            if thermostat.entity_id == entity_id:
                value = {"id": thermostat.unique_id, "lock": service.data[ATTR_KEYPAD_LOCK]}
                thermostat.set_keypad_lock(value)
                thermostat.schedule_update_ha_state(True)
                break

    def set_second_display_service(service):
        """Set to outside or setpoint temperature display"""
        entity_id = service.data[ATTR_ENTITY_ID]
        value = {}
        for thermostat in entities:
            if thermostat.entity_id == entity_id:
                value = {"id": thermostat.unique_id, "display": service.data[ATTR_DISPLAY]}
                thermostat.set_second_display(value)
                thermostat.schedule_update_ha_state(True)
                break

    def set_backlight_state_service(service):
        """Set to outside or setpoint temperature display"""
        entity_id = service.data[ATTR_ENTITY_ID]
        value = {}
        for thermostat in entities:
            if thermostat.entity_id == entity_id:
                value = {"id": thermostat.unique_id, "state": service.data[ATTR_STATE]}
                thermostat.set_backlight_state(value)
                thermostat.schedule_update_ha_state(True)
                break

    def set_backlight_idle_service(service):
        """Set to outside or setpoint temperature display"""
        entity_id = service.data[ATTR_ENTITY_ID]
        value = {}
        for thermostat in entities:
            if thermostat.entity_id == entity_id:
                value = {"id": thermostat.unique_id, "level": service.data[ATTR_LEVEL]}
                thermostat.set_backlight_idle(value)
                thermostat.schedule_update_ha_state(True)
                break

    def set_basic_data_service(service):
        """Set to outside or setpoint temperature display"""
        entity_id = service.data[ATTR_ENTITY_ID]
        value = {}
        for thermostat in entities:
            if thermostat.entity_id == entity_id:
                value = {"id": thermostat.unique_id}
                thermostat.set_basic_data(value)
                thermostat.schedule_update_ha_state(True)
                break

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_OUTSIDE_TEMPERATURE,
        set_outside_temperature_service,
        schema=SET_OUTSIDE_TEMPERATURE_SCHEMA,
    )
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_KEYPAD_LOCK,
        set_keypad_lock_service,
        schema=SET_KEYPAD_LOCK_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SECOND_DISPLAY,
        set_second_display_service,
        schema=SET_SECOND_DISPLAY_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_BACKLIGHT_IDLE,
        set_backlight_idle_service,
        schema=SET_BACKLIGHT_IDLE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_BACKLIGHT_STATE,
        set_backlight_state_service,
        schema=SET_BACKLIGHT_STATE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_BASIC_DATA,
        set_basic_data_service,
        schema=SET_BASIC_DATA_SCHEMA,
    )

class SinopeThermostat(ClimateEntity):
    """Implementation of a Sinope thermostat."""

    def __init__(self, data, device_id, name, device_type, server):
        """Initialize."""
        self._name = name
        self._server = server
        self._type = device_type
        self._client = data.sinope_client
        self._id = device_id
        self._wattage = None
        self._wattage_override = None
        self._min_temp = None
        self._max_temp = None
        self._target_temp = None
        self._target_temp_before = None
        self._cur_temp = None
        self._cur_temp_before = None
        self._rssi = None
        self._alarm = None
        self._operation_mode = 2
        self._heat_level = None
        self._heat_level_before = None
        self._outside_temperature = None
        self._keypad = "Unlocked"
        self._second_display = None
        self._backlight_idle = None
        self._backlight_state = None
        _LOGGER.debug("Setting up %s: %s", self._name, self._id)

    def update(self):
        """Get the latest data from Sinope and update the state."""
        start = time.time()
        device_data = self._client.get_climate_device_data(self._server, self._id)
        end = time.time()
        elapsed = round(end - start, 3)
        _LOGGER.debug("Updating %s (%s sec): %s",
            self._name, elapsed, device_data)

        self._cur_temp_before = self._cur_temp
        self._cur_temp = float(device_data["temperature"]) if \
            device_data["temperature"] is not None else self._cur_temp_before
        self._target_temp_before = self._target_temp
        self._target_temp = float(device_data["setpoint"]) if \
            device_data["setpoint"] is not None else self._target_temp_before
        self._heat_level_before = self._heat_level
        self._heat_level = device_data["heatLevel"] if \
            device_data["heatLevel"] is not None else self._heat_level_before
        self._alarm = device_data["alarm"]
        self._rssi = device_data["rssi"]
        self._operation_mode = device_data["mode"] if \
            device_data["mode"] is not None else SINOPE_MODE_MANUAL

        device_info = self._client.get_climate_device_info(self._server, self._id)
        self._wattage = device_info["wattage"]
        self._wattage_override = device_info["wattageOverride"]
        self._min_temp = device_info["tempMin"]
        self._max_temp = device_info["tempMax"]
        self._keypad = "Unlocked" if device_info["keypad"] == 0 else "Locked"
        if device_info["display2"] is not None:
            self._second_display = "Setpoint" if device_info["display2"] == 0 else "Outside"
        if device_info["backlight_state"] == 0:
            self._backlight_state = "Full On"
        elif device_info["backlight_state"] == 1:
            self._backlight_state = "Variable Idle"
        elif device_info["backlight_state"] == 2:
            self._backlight_state = "Off Idle"
        elif device_info["backlight_state"] == 3:
            self._backlight_state = "Always Variable"
        else:
            self._backlight_state = "Unknown"
        self._backlight_idle = "Off" if device_info["backlight_idle"] == 0 else "On"
        return

    @property
    def server(self):
        """Return the server number where the device is connected"""
        return self._server

    @property
    def unique_id(self):
        """Return unique ID based on Sinope device ID."""
        return self._id

    @property
    def device_class(self):
        """Return HA device class."""
        return "heat"

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._name

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {
                (sinope.DOMAIN, self.unique_id)
            },
            "name": self.name,
            "manufacturer": "Sinopé",
            "device_id": self._id,
        }

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {'alarm': self._alarm,
                'keypad': self._keypad,
                'backlight state': self._backlight_state,
                'backlight_idle': self._backlight_idle,
                'display2': self._second_display,
                'heat_level': self._heat_level,
                'rssi': self._rssi,
                'wattage': self._wattage,
                'wattage_override': self._wattage_override,
                'server': self._server,
                'id': self._id}

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def min_temp(self):
        """Return the min temperature."""
        return self._min_temp

    @property
    def max_temp(self):
        """Return the max temperature."""
        return self._max_temp

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def keypad(self):
        """Return the state of keypad, Unlocked or Locked."""
        return self._keypad

    @property
    def second_display(self):
        """Return the second display state, outside or setpoint"""
        return self._second_display

    @property
    def backlight_idle(self):
        """Return the state of keypad, Unlocked or Locked."""
        return self._backlight_idle

    @property
    def backlight_state(self):
        """Return the second display state, outside or setpoint"""
        return self._backlight_state

    @property
    def hvac_mode(self):
        """Return current operation"""
        if self._operation_mode == SINOPE_MODE_OFF:
            return HVAC_MODE_OFF
        elif self._operation_mode in [SINOPE_MODE_AUTO, 
                                      SINOPE_MODE_AUTO_BYPASS]:
            return HVAC_MODE_AUTO
        else:
            return HVAC_MODE_HEAT

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return SUPPORTED_HVAC_MODES

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._cur_temp

    @property
    def target_temperature (self):
        """Return the temperature we try to reach."""
        return self._target_temp

    @property
    def outside_temperature (self):
        """Return the outside temperature we try to set."""
        return self._outside_temperature

    @property
    def preset_modes(self):
        """Return available preset modes."""
        return PRESET_MODES

    @property
    def preset_mode(self):
        """Return current preset mode."""
        if self._operation_mode & SINOPE_BYPASS_FLAG == SINOPE_BYPASS_FLAG:
            return PRESET_BYPASS
        elif self._operation_mode == SINOPE_MODE_AWAY:
            return PRESET_AWAY
        else:
            return PRESET_NONE

    @property
    def hvac_action(self):
        """Return current HVAC action."""
        if self._operation_mode == SINOPE_MODE_OFF:
            return CURRENT_HVAC_OFF
        elif self._heat_level == 0:
            return CURRENT_HVAC_IDLE
        else:
            return CURRENT_HVAC_HEAT

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._client.set_temperature(self._server, self._id, temperature)
        self._target_temp = temperature

    def set_outside_temperature(self, value):
        """Send command to set new outside temperature."""
        outside_temperature = value["temperature"]
        entity = value["id"]
        if outside_temperature is None:
            return
        self._client.set_hourly_report(self._server, entity, outside_temperature)
        self._outside_temperature = outside_temperature

    async def async_set_outside_temperature(self, value):
        """ set outside temperature on second thermostat display"""
        outside_temperature = value["temperature"]
        entity = value["id"]
        self._client.set_hourly_report(
            self._server, entity, outside_temperature)
        self._outside_temperature = outside_temperature

    def set_keypad_lock(self, value):
        """Lock or unlock device's keypad, lock = lock, unlock = unlock"""
        lock = value["lock"]
        entity = value["id"]
        if lock == "lock":
            lock_commande = 1
            lock_name = "Locked"
        else:
            lock_commande = 0
            lock_name = "Unlocked"
        self._client.set_keyboard_lock(
            self._server, entity, lock_commande)
        self._keypad = lock_name

    def set_second_display(self, value):
        """Set thermostat second display between outside and setpoint temperature"""
        display = value["display"]
        entity = value["id"]
        if display == "out":
            display_commande = 1
            display_name = "Outside"
        else:
            display_commande = 0
            display_name = "Setpoint"
        self._client.set_second_display(
            self._server, entity, display_commande)
        self._second_display = display_name

    def set_backlight_idle(self, value):
        """Set thermostat back light to on/off"""
        level = value["level"]
        entity = value["id"]
        if level == 0:
            idle_name = "Off"
        else:
            idle_name = "On"
        self._client.set_backlight_idle(
            self._server, entity, level)
        self._backlight_idle = idle_name

    def set_backlight_state(self, value):
        """Set thermostat back light state"""
        state = value["state"]
        entity = value["id"]
        if state == 0:
            state_name = "Full on"
        elif state == 1:
            state_name = "Variable idle"
        elif state == 2:
            state_name = "Off idle"
        else:
            state_name = "Always Variable"
        self._client.set_backlight_idle(
            self._server, entity, state)
        self._backlight_state = state_name

    def set_basic_data(self, value):
        """Send command to set new outside temperature."""
        entity = value["id"]
        self._client.set_daily_report(self, self._server)

    def set_hvac_mode(self, hvac_mode):
        """Set new hvac mode."""
        self._client.send_time(self._server, self._id)
        if hvac_mode == HVAC_MODE_OFF:
            self._client.set_mode(self._server, self._id, self._type, SINOPE_MODE_OFF)
        elif hvac_mode == HVAC_MODE_HEAT:
            self._client.set_mode(self._server, self._id, self._type, SINOPE_MODE_MANUAL)
        elif hvac_mode == HVAC_MODE_AUTO:
            self._client.set_mode(self._server, self._id, self._type, SINOPE_MODE_AUTO)
        else:
            _LOGGER.error("Unable to set hvac mode: %s.", hvac_mode)

    def set_preset_mode(self, preset_mode):
        """Activate a preset."""
        if preset_mode == self.preset_mode:
            return
        if preset_mode == PRESET_AWAY:
            """Set away mode on device, away_on = 2 away_off =0"""
            self._client.set_away_mode(self._server, self._id, 2)
        elif preset_mode == PRESET_BYPASS:
            if self._operation_mode in SINOPE_BYPASSABLE_MODES:
                self._client.set_away_mode(self._server, self._id, 0)      
                self._client.set_mode(self._server, self._id, self._type, self._operation_mode | 
                SINOPE_BYPASS_FLAG)
        elif preset_mode == PRESET_NONE:
            # Re-apply current hvac_mode without any preset
            self._client.set_away_mode(self._server, self._id, 0)
            self.set_hvac_mode(self.hvac_mode)
        else:
            _LOGGER.error("Unable to set preset mode: %s.", preset_mode)
