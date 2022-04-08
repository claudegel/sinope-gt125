"""
Support for Sinope switch.
family 120 = load controller device, RM3250RF and RM3200RF
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

from homeassistant.components.switch import (
    SwitchEntity,
)

from homeassistant.helpers import (
    config_validation as cv,
    discovery,
    entity_platform,
    service,
    entity_component,
    entity_registry,
    device_registry,
)

from homeassistant.core import (
    ServiceCall,
    callback,
)

from homeassistant.const import (
    ATTR_ENTITY_ID,
)

from datetime import timedelta
from homeassistant.helpers.event import track_time_interval
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.components.sensor import SensorDeviceClass

from .const import (
    DOMAIN,
    ATTR_EVENT_TIMER,
    ATTR_KEYPAD_LOCK,
    SUPPORT_EVENT_TIMER,
    SUPPORT_KEYPAD_LOCK,
    SERVICE_SET_SWITCH_EVENT_TIMER,
    SERVICE_SET_SWITCH_KEYPAD_LOCK,
    SERVICE_SET_SWITCH_BASIC_DATA,
)

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = (SUPPORT_KEYPAD_LOCK, SUPPORT_EVENT_TIMER)

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

IMPLEMENTED_DEVICE_TYPES = [120] #power control device

SET_SWITCH_KEYPAD_LOCK_SCHEMA = vol.Schema(
    {
         vol.Required(ATTR_ENTITY_ID): cv.entity_id,
         vol.Required(ATTR_KEYPAD_LOCK): vol.In(["lock", "unlock"]),
    }
)

SET_SWITCH_EVENT_TIMER_SCHEMA = vol.Schema(
    {
         vol.Required(ATTR_ENTITY_ID): cv.entity_id,
         vol.Required(ATTR_EVENT_TIMER): vol.All(
             vol.Coerce(int), vol.Range(min=0, max=255)
         ),
    }
)

SET_SWITCH_BASIC_DATA_SCHEMA = vol.Schema(
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
    """Set up the Sinope switch."""
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
            entities.append(SinopeSwitch(data, device_id, device_name, device_type, server))
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
                entities.append(SinopeSwitch(data, device_id, device_name, device_type, server))
            if i == tot2-1:
                break
            i = i + 1

    add_entities(entities, True)

    def set_switch_keypad_lock_service(service):
        """ lock/unlock keypad device"""
        entity_id = service.data[ATTR_ENTITY_ID]
        value = {}
        for power in entities:
            if power.entity_id == entity_id:
                value = {"id": power.unique_id, "lock": service.data[ATTR_KEYPAD_LOCK]}
                power.set_keypad_lock(value)
                power.schedule_update_ha_state(True)
                break

    def set_switch_event_timer_service(service):
        """ set event timer lenght"""
        entity_id = service.data[ATTR_ENTITY_ID]
        value = {}
        for power in entities:
            if power.entity_id == entity_id:
                value = {"id": power.unique_id, "time": service.data[ATTR_EVENT_TIMER]}
                power.set_event_timer(value)
                power.schedule_update_ha_state(True)
                break

    def set_switch_basic_data_service(service):
        """Set to outside or setpoint temperature display"""
        entity_id = service.data[ATTR_ENTITY_ID]
        value = {}
        for power in entities:
            if power.entity_id == entity_id:
                value = {"id": power.unique_id}
                power.set_basic_data(value)
                power.schedule_update_ha_state(True)
                break

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SWITCH_KEYPAD_LOCK,
        set_switch_keypad_lock_service,
        schema=SET_SWITCH_KEYPAD_LOCK_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SWITCH_EVENT_TIMER,
        set_switch_event_timer_service,
        schema=SET_SWITCH_EVENT_TIMER_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SWITCH_BASIC_DATA,
        set_switch_basic_data_service,
        schema=SET_SWITCH_BASIC_DATA_SCHEMA,
    )

class SinopeSwitch(SwitchEntity):
    """Implementation of a Sinope switch."""

    def __init__(self, data, device_id, name, device_type, server):
        """Initialize."""
        self._name = name
        self._server = server
        self._type = device_type
        self._client = data.sinope_client
        self._id = device_id
        self._wattage = 0
        self._brightness = None
        self._operation_mode = 1
        self._alarm = None
        self._current_power_w = None
        self._rssi = None
        self._event_timer = 0
        self._keypad = "Unlocked"
        _LOGGER.debug("Setting up %s: %s", self._name, self._id)

    def update(self):
        """Get the latest data from Sinope and update the state."""
        start = time.time()
        device_data = self._client.get_switch_device_data(self._server, self._id)
        end = time.time()
        elapsed = round(end - start, 3)
        _LOGGER.debug("Updating %s (%s sec): %s",
            self._name, elapsed, device_data)
        self._brightness = device_data["intensity"] if \
                device_data["intensity"] is not None else 0
        self._operation_mode = device_data["mode"] if \
                device_data["mode"] is not None else 1 #STATE_MANUAL
        self._alarm = device_data["alarm"]
        self._current_power_w = device_data["powerWatt"] if \
                device_data["powerWatt"] is not None else 0
        self._rssi = device_data["rssi"]
        device_info = self._client.get_switch_device_info(self._server, self._id)
        self._wattage = device_info["wattage"] if \
                device_info["wattage"] is not None else 0.0
        self._event_timer = device_info["timer"] if \
                device_info["timer"] is not None else 0
        self._keypad = "Unlocked" if device_info["keypad"] == 0 else "Locked"
        return
#        _LOGGER.warning("Cannot update %s: %s", self._name, device_data)
#        _LOGGER.warning("Cannot update %s: %s", self._name, device_info)

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
        return SensorDeviceClass.POWER

    @property
    def name(self):
        """Return the name of the switch."""
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
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property  
    def is_on(self):
        """Return current operation i.e. ON, OFF """
        return self._brightness != 0

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._client.set_brightness(self._server, self._id, 100)
        self._brightness = 100

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._client.set_brightness(self._server, self._id, 0)
        self._brightness = 0

    @property
    def keypad (self):
        """Return the keypad state of the device"""
        return self._keypad

    @property
    def event_timer (self):
        """Return the event timer state of the device"""
        return self._event_timer

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {'alarm': self._alarm,
                'operation_mode': self.operation_mode,
                'rssi': self._rssi,
                'wattage': self._wattage,
                'event timer': self._event_timer,
                'keypad': self._keypad,
                'server': self._server,
                'id': self._id,
                }

    @property
    def operation_mode(self):
        return self.to_hass_operation_mode(self._operation_mode)

    @property
    def is_standby(self):
        """Return true if device is in standby."""
        return self._current_power_w == 0

    def set_keypad_lock(self, value):
        """Lock or unlock device's keypad, lock = locked, unlock = unlocked"""
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

    def set_event_timer(self, value):
        """Set event timer lenght, 0 = off, 1 to 255 = lenght"""
        time = value["time"]
        entity = value["id"]
        if time == 0:
            time_name = "off"
        else:
            time_name = "on"
        self._client.set_event_timer(
            self._server, entity, time)
        self._event_timer = time_name

    def set_basic_data(self, value):
        """Send command to set new outside temperature."""
        entity = value["id"]
        self._client.set_daily_report(self._server)

    def to_hass_operation_mode(self, mode):
        """Translate Sinope operation modes to hass operation modes."""
        if mode in SINOPE_TO_HA_STATE:
            return SINOPE_TO_HA_STATE[mode]
        _LOGGER.error("Operation mode %s could not be mapped to hass", mode)
        return None
