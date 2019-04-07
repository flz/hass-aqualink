"""
Support for Aqualink pool feature switches.
"""
import logging
import time
from typing import TYPE_CHECKING

from homeassistant.components.switch import DOMAIN, SwitchDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SWITCHES
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN as AQUALINK_DOMAIN

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

if TYPE_CHECKING:
    from iaqualink import AqualinkToggle


async def async_setup_entry(hass: HomeAssistantType,
                            config_entry: ConfigEntry,
                            async_add_entities) -> None:
    """Set up discovered switches."""
    devs = []
    for dev in hass.data[AQUALINK_DOMAIN][DOMAIN]:
        devs.append(HassAqualinkToggle(dev))
    async_add_entities(devs, True)


class HassAqualinkToggle(SwitchDevice):
    def __init__(self, dev: 'AqualinkToggle'):
        SwitchDevice.__init__(self)
        self.dev = dev

    @property
    def name(self) -> str:
        return self.dev.label

    @property
    def icon(self) -> str:
        if self.name == 'Cleaner':
            return 'mdi:robot-vacuum'
        elif self.name == 'Waterfall' or self.name.endswith('Dscnt'):
            return 'mdi:fountain'
        elif self.name.endswith('Pump') or self.name.endswith('Blower'):
            return 'mdi:fan'
        elif self.name.endswith('Heater'):
            return 'mdi:radiator'

    @property
    def is_on(self) -> bool:
        return self.dev.is_on

    async def async_turn_on(self) -> None:
        await self.dev.turn_on()

    async def async_turn_off(self) -> None:
        await self.dev.turn_off()

    async def async_update(self) -> None:
        return None
        # Disable for now since throttling on the API side doesn't work.
        # await self.dev.system.update()
