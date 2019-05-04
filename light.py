"""
Support for Aqualink pool lights.
"""
import logging
import time
from typing import TYPE_CHECKING

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_EFFECT, SUPPORT_BRIGHTNESS, SUPPORT_EFFECT, Light)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LIGHTS
from homeassistant.helpers.typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['aqualink']

AQUALINK_DOMAIN = 'aqualink'

PARALLEL_UPDATES = 0

if TYPE_CHECKING:
    from iaqualink import AqualinkLight, AqualinkLightEffect


async def async_setup_entry(hass: HomeAssistantType,
                            config_entry: ConfigEntry,
                            async_add_entities) -> None:
    """Set up discovered switches."""
    devs = []
    for dev in hass.data[AQUALINK_DOMAIN][CONF_LIGHTS]:
        devs.append(HassAqualinkLight(dev))
    async_add_entities(devs, True)


class HassAqualinkLight(Light):
    def __init__(self, dev: 'AqualinkLight'):
        Light.__init__(self)
        self.dev = dev
        self._supported_features = None
     
    @property
    def name(self) -> str:
        return self.dev.label

    @property
    def icon(self) -> str:
        return 'mdi:brightness-6'

    @property
    def is_on(self) -> bool:
        return self.dev.is_on

    async def async_turn_on(self, **kwargs) -> None:
        from iaqualink import AqualinkLightEffect

        brightness = kwargs.get(ATTR_BRIGHTNESS, None)
        effect = kwargs.get(ATTR_EFFECT, None)

        # For now I'm assuming lights support either effects or brightness.
        if effect:
            effect = AqualinkLightEffect[effect].value
            await self.dev.set_effect(effect)
        elif brightness:
            # Aqualink supports percentages in 25% increments.
            pct = int(round(brightness * 4.0 / 255)) * 25
            await self.dev.set_brightness(pct)
        else:
            await self.dev.turn_on()
     
    async def async_turn_off(self) -> None:
        await self.dev.turn_off()

    @property
    def brightness(self) -> int:
        return self.dev.brightness * 255 / 100

    @property
    def effect(self) -> str:
        from iaqualink import AqualinkLightEffect

        name = AqualinkLightEffect(self.dev.effect).name
        return name

    @property
    def effect_list(self) -> list:
        from iaqualink import AqualinkLightEffect

        effects = list(AqualinkLightEffect.__members__.keys())
        return effects
     
    async def async_update(self) -> None:
        if self._supported_features is None:
            self.get_features()
        return None
        # Disable for now since throttling on the API side doesn't work.
        # await self.dev.system.update()

    @property
    def supported_features(self) -> int:
        return self._supported_features
            
    def get_features(self) -> None:
        self._supported_features = 0

        if self.dev.is_dimmer:
            self._supported_features |= SUPPORT_BRIGHTNESS

        if self.dev.is_color:
            self._supported_features |= SUPPORT_EFFECT
