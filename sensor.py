"""
Support for Aqualink temperature sensors.
"""
import logging
import time

from .api import AqualinkSensor
from homeassistant.helpers.entity import Entity
from homeassistant.const import (
    CONF_SENSORS, DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_TEMPERATURE, TEMP_FAHRENHEIT)
import homeassistant.helpers.device_registry as dr

AQUALINK_DOMAIN = 'aqualink'

DEPENDENCIES = ['aqualink']

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up discovered switches."""
    devs = []
    for dev in hass.data[AQUALINK_DOMAIN][CONF_SENSORS]:
        devs.append(HassAqualinkSensor(dev))

    async_add_entities(devs, True)

    return True


class HassAqualinkSensor(Entity):
    def __init__(self, dev):
        Entity.__init__(self)
        self.dev = dev
     
    @property
    def name(self):
        return self.dev.name

    @property
    def unit_of_measurement(self):
        return TEMP_FAHRENHEIT

    @property
    def state(self):
        return self.dev.value
    
    @property 
    def device_class(self):
        return DEVICE_CLASS_TEMPERATURE
     
    def update(self):
        return self.dev.update()
            
