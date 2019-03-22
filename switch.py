"""
Support for Aqualink pool feature switches.
"""
import logging
import time
from typing import TYPE_CHECKING

from homeassistant.components.switch import SwitchDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SWITCHES
from homeassistant.helpers.typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['aqualink']

AQUALINK_DOMAIN = 'aqualink'

if TYPE_CHECKING:
    from .api import AqualinkSwitch


async def async_setup_entry(hass: HomeAssistantType,
                            config_entry: ConfigEntry,
                            async_add_entities) -> None:
    """Set up discovered switches."""
    devs = []
    for dev in hass.data[AQUALINK_DOMAIN][CONF_SWITCHES]:
        devs.append(HassAqualinkSwitch(dev))
    async_add_entities(devs, True)


class HassAqualinkSwitch(SwitchDevice):
    def __init__(self, dev: 'AqualinkSwitch'):
        SwitchDevice.__init__(self)
        self.dev = dev
     
    @property
    def name(self) -> str:
        return self.dev.name

    @property
    def is_on(self) -> bool:
        return self.dev.is_on

    def turn_on(self) -> None:
        return self.dev.turn_on()
     
    def turn_off(self) -> None:
        return self.dev.turn_off()
     
    def update(self) -> None:
        self.dev.update()