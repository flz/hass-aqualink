"""
Support for Aqualink pool lights.
"""
import logging
import time

from .api import AqualinkLight
from homeassistant.components.light import Light
from homeassistant.const import CONF_LIGHTS
import homeassistant.helpers.device_registry as dr

AQUALINK_DOMAIN = 'aqualink'

DEPENDENCIES = ['aqualink']

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up discovered switches."""
    devs = []
    for dev in hass.data[AQUALINK_DOMAIN][CONF_LIGHTS]:
        devs.append(HassAqualinkLight(dev))

    async_add_entities(devs, True)

    return True


class HassAqualinkLight(Light):
    def __init__(self, dev):
        Light.__init__(self)
        self.dev = dev
     
    @property
    def name(self):
        return self.dev.name

    @property
    def is_on(self):
        return self.dev.is_on

    def turn_on(self):
        return self.dev.turn_on()
     
    def turn_off(self):
        return self.dev.turn_off()
     
    def update(self):
        return self.dev.update()
            
