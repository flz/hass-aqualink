"""
Support for Aqualink temperature sensors.
"""
import logging
import time
from typing import TYPE_CHECKING, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_SENSORS, DEVICE_CLASS_TEMPERATURE, STATE_OFF, STATE_ON,
    TEMP_FAHRENHEIT)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['aqualink']

AQUALINK_DOMAIN = 'aqualink'

PARALLEL_UPDATES = 0

if TYPE_CHECKING:
    from .api import AqualinkSensor


async def async_setup_entry(hass: HomeAssistantType,
                            config_entry: ConfigEntry,
                            async_add_entities) -> None:
    """Set up discovered sensors."""
    devs = []
    for dev in hass.data[AQUALINK_DOMAIN][CONF_SENSORS]:
        devs.append(HassAqualinkSensor(dev))
    async_add_entities(devs, True)


class HassAqualinkSensor(Entity):
    def __init__(self, dev: 'AqualinkSensor'):
        Entity.__init__(self)
        self.dev = dev
     
    @property
    def name(self) -> str:
        return self.dev.label

    @property
    def unit_of_measurement(self) -> str:
        return TEMP_FAHRENHEIT

    @property
    def state(self) -> str:
        return int(self.dev.state) if self.dev.state else None
    
    @property 
    def device_class(self) -> Optional[str]:
        if self.dev.name.endswith('_temp'):
            return DEVICE_CLASS_TEMPERATURE
        return None

    @property
    def icon(self) -> Optional[str]:
        if self.dev.name.endswith('_temp'):
            return 'mdi:thermometer'
        return None
     
    async def async_update(self) -> None:
        return None
        # Disable for now since throttling on the API side doesn't work.
        # await self.dev.system.update()