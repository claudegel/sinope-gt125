"""
Support for Sinope light switch/dimmer.
family 102 = light switch SW2500RF
family 112 = light dimmer DM2500RF
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

from homeassistant.components.light import (
    LightEntity,
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    SUPPORT_BRIGHTNESS,
)

from homeassistant.core import (
    ServiceCall,
    callback,
)

from homeassistant.const import (
    ATTR_ENTITY_ID,
)

from homeassistant.helpers import (
    config_validation as cv,
    discovery,
    entity_platform,
    service,
)

from datetime import timedelta
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
    ATTR_TIMER,
    ATTR_KEYPAD_LOCK,
    SUPPORT_TIMER,
    SUPPORT_KEYPAD_LOCK,
    SERVICE_SET_TIMER,
    SERVICE_SET_KEYPAD_LOCK,
)

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = (SUPPORT_KEYPAD_LOCK | SUPPORT_TIMER)
DIMMER_SUPPORT_FLAGS = (SUPPORT_KEYPAD_LOCK | SUPPORT_TIMER | SUPPORT_BRIGHTNESS)

DEFAULT_NAME = 'sinope'
DATA_DOMAIN = 'data_' + DOMAIN

STATE_AUTO = 'auto'
STATE_MANUAL = 'manual'
STATE_AWAY = 'away'
STATE_STANDBY = 'bypass'
SINOPE_TO_HA_STATE = {
    1: STATE_MANUAL,
    2: STATE_AUTO,
    3: STATE_AWAY,
    130: STATE_STANDBY
}

DEVICE_TYPE_DIMMER = [112]
DEVICE_TYPE_LIGHT = [102]
IMPLEMENTED_DEVICE_TYPES = DEVICE_TYPE_LIGHT + DEVICE_TYPE_DIMMER

SET_KEYPAD_LOCK_SCHEMA = vol.Schema(
    {
         vol.Required(ATTR_ENTITY_ID): cv.entity_id,
         vol.Required(ATTR_KEYPAD_LOCK): cv.string,
    }
)

SET_TIMER_SCHEMA = vol.Schema(
    {
         vol.Required(ATTR_ENTITY_ID): cv.entity_id,
         vol.Required(ATTR_TIMER): vol.All(
             vol.Coerce(int), vol.Range(min=0, max=255)
         ),
    }
)

def setup_platform(
    hass: HomeAssistantType,
    config_entry,
    add_entities,
    discovery_info = None,
) -> None:
    """Set up the sinope light."""
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
            device_name = '{} {} {}'.format(DEFAULT_NAME, 
                "dimmer" if x in DEVICE_TYPE_DIMMER 
                else "light", dev_list[i][1])
            device_id = "{}".format(dev_list[i][0])
            watt = "{}".format(dev_list[i][3])
            device_type = "{}".format(int(dev_list[i][2]))
            server = 1
            entities.append(SinopeLight(data, device_id, device_name, watt, device_type, server))
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
                device_name = '{} {} {}'.format(DEFAULT_NAME, 
                    "dimmer" if x in DEVICE_TYPE_DIMMER 
                    else "light", dev_list_2[i][1])
                device_id = "{}".format(dev_list_2[i][0])
                watt = "{}".format(dev_list_2[i][3])
                device_type = "{}".format(int(dev_list_2[i][2]))
                server = 2
                entities.append(SinopeLight(data, device_id, device_name, watt, device_type, server))
            if i == tot2-1:
                break
            i = i + 1

    add_entities(entities, True)

    def set_keypad_lock_service(service):
        """ lock/unlock keypad device"""
        entity_id = service.data[ATTR_ENTITY_ID]
        value = {}
        for light in entities:
            if light.entity_id == entity_id:
                value = {"id": light.unique_id, "lock": service.data[ATTR_KEYPAD_LOCK]}
                light.set_keypad_lock(value)
                light.schedule_update_ha_state(True)
                break

    def set_timer_service(service):
        """ lock/unlock keypad device"""
        entity_id = service.data[ATTR_ENTITY_ID]
        value = {}
        for light in entities:
            if light.entity_id == entity_id:
                value = {"id": light.unique_id, "time": service.data[ATTR_TIMER]}
                light.set_timer(value)
                light.schedule_update_ha_state(True)
                break

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_KEYPAD_LOCK,
        set_keypad_lock_service,
        schema=SET_KEYPAD_LOCK_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_TIMER,
        set_timer_service,
        schema=SET_TIMER_SCHEMA,
    )

def brightness_to_percentage(brightness):
    """Convert brightness from absolute 0..255 to percentage."""
    return int((brightness * 100.0) / 255.0)

def brightness_from_percentage(percent):
    """Convert percentage to absolute value 0..255."""
    return int((percent * 255.0) / 100.0)

class SinopeLight(LightEntity):
    """Implementation of a Sinope light."""

    def __init__(self, data, device_id, name, wattage, device_type, server):
        """Initialize."""
        self._name = name
        self._server = server
        self._type = int(device_type)
        self._client = data.sinope_client
        self._id = device_id
        self._wattage_override = wattage
        self._brightness_pct = 0
        self._operation_mode = 1
        self._alarm = None
        self._rssi = None
        self._timer = 0
        self._keypad = "Unlocked"
        self._is_dimmable = int(device_type) in DEVICE_TYPE_DIMMER
        _LOGGER.debug("Setting up %s: %s", self._name, self._id)
        
    def update(self):
        """Get the latest data from Sinope and update the state."""
        start = time.time()
        device_data = self._client.get_light_device_data(self._server, self._id)
        end = time.time()
        elapsed = round(end - start, 3)
        _LOGGER.debug("Updating %s (%s sec): %s",
            self._name, elapsed, device_data)
        self._brightness_pct = device_data["intensity"] if \
            device_data["intensity"] is not None else 0.0
        self._operation_mode = device_data["mode"] if \
            device_data["mode"] is not None else 1
        self._alarm = device_data["alarm"]
        self._rssi = device_data["rssi"]
        device_info = self._client.get_light_device_info(self._server, self._id)
        self._timer = device_info["timer"] if \
            device_info["timer"] is not None else 0
        self._keypad = "Unlocked" if device_info["keypad"] == 0 else "Locked"
        return
#        _LOGGER.warning("Cannot update %s: %s", self._name, device_info)
        
    @property
    def supported_features(self):
        """Return the list of supported features."""
        if self._is_dimmable:
            return DIMMER_SUPPORT_FLAGS
        return SUPPORT_FLAGS

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
        return "light"

    @property
    def name(self):
        """Return the name of the light."""
        return self._name

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "Sinopé",
            "device_id": self._id,
        }

    @property
    def brightness(self):
        """Return intensity of light"""
        return brightness_from_percentage(self._brightness_pct)

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._brightness_pct != 0

    @property
    def keypad (self):
        """Return the keypad state of the device"""
        return self._keypad

    @property
    def timer (self):
        """Return the timer state of the device"""
        return self._timer

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        data = {}
        if self._is_dimmable:
            data = {ATTR_BRIGHTNESS_PCT: self._brightness_pct}
        data.update({'alarm': self._alarm,
                     'operation_mode': self.operation_mode,
                     'rssi': self._rssi,
                     'wattage_override': self._wattage_override,
                     'keypad': self._keypad,
                     'timer': self._timer,
                     'server': self._server,
                     'id': self._id,
                     })
        return data

    @property
    def operation_mode(self):
        return self.to_hass_operation_mode(self._operation_mode)

    # For the turn_on and turn_off functions, we would normally check if the
    # the requested state is different from the actual state to issue the 
    # command. But since we update the state every 5 minutes, there is good
    # chance that the current stored state doesn't match with real device 
    # state. So we force the set_brightness each time.
    def turn_on(self, **kwargs):
        """Turn the light on."""
        brightness_pct = 100
        if kwargs.get(ATTR_BRIGHTNESS):
            brightness_pct = \
                brightness_to_percentage(int(kwargs.get(ATTR_BRIGHTNESS)))
        elif self._is_dimmable:
            brightness_pct = 101 # Sets the light to last known brightness.
        self._client.set_brightness(self._server, self._id, brightness_pct)

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self._client.set_brightness(self._server, self._id, 0)

    def set_keypad_lock(self, value):
        """Lock or unlock device's keypad, True = lock, False = unlock"""
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

    def set_timer(self, value):
        """Set timer lenght, 0 = off, 1 to 255 = lenght"""
        time = value["time"]
        entity = value["id"]
        if time == 0:
            time_name = "off"
        else:
            time_name = "on"
        self._client.set_timer(
            self._server, entity, time)
        self._timer = time_name

    def to_hass_operation_mode(self, mode):
        """Translate sinope operation modes to hass operation modes."""
        if mode in SINOPE_TO_HA_STATE:
            return SINOPE_TO_HA_STATE[mode]
        _LOGGER.error("Operation mode %s could not be mapped to hass", mode)
        return None
