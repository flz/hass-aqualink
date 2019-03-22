"""Support for Aqualink Thermostats."""
import logging
from typing import TYPE_CHECKING, List, Optional

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    DOMAIN, STATE_HEAT, SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_OPERATION_MODE)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ON, STATE_OFF, ATTR_TEMPERATURE, TEMP_FAHRENHEIT)
from homeassistant.helpers.typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['aqualink']

AQUALINK_DOMAIN = 'aqualink'

if TYPE_CHECKING:
    from .api import (
        AqualinkSensor, AqualinkSwitch, AqualinkThermostat)


async def async_setup_entry(hass: HomeAssistantType,
                            config_entry: ConfigEntry,
                            async_add_entities) -> None:
    """Set up discovered switches."""
    devs = []
    for dev in hass.data[AQUALINK_DOMAIN][DOMAIN]:
        devs.append(HassAqualinkThermostat(dev))
    async_add_entities(devs, True)


class HassAqualinkThermostat(ClimateDevice):
    def __init__(self, dev: 'AqualinkThermostat'):
        """Initialize the thermostat."""
        self.dev = dev

    @property
    def name(self) -> str:
        """Return the name of the thermostat."""
        return self.dev.name

    def update(self) -> None:
        """Get the latest state from the thermostat."""
        self.dev.update()

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        flags = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE)
        return flags

    @property
    def operation_list(self) -> List[str]:
        return [STATE_HEAT, STATE_OFF]
    
    @property
    def pump(self) -> 'AqualinkSwitch':
        pump = self.name.lower().replace(' temp', '_pump')
        return self.dev.aqualink._devices[pump]

    @property
    def current_operation(self) -> str:
        # Since we don't actually know if it's heating, just assume it's
        # heating all the time. 
        if self.heater.state:
            return STATE_HEAT
        else:
            return STATE_OFF

    def set_operation_mode(self, operation_mode: str) -> None:
        if operation_mode == STATE_HEAT:
            self.turn_on()
        elif operation_mode == STATE_OFF:
            self.turn_off()
        else:
            _LOGGER.warning(f"Unknown operation mode: {operation_mode}")

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return TEMP_FAHRENHEIT

    @property
    def min_temp(self) -> int:
        return 34

    @property
    def max_temp(self) -> int:
        return 104

    @property
    def target_temperature(self) -> int:
        return self.dev.state

    def set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        self.dev.set_target(int(kwargs[ATTR_TEMPERATURE]))

    @property
    def sensor(self) -> 'AqualinkSensor':
        sensor = self.name.lower().replace(' ', '_')
        return self.dev.aqualink._devices[sensor]

    @property
    def current_temperature(self) -> Optional[int]:
        """Return the current temperature."""
        return self.sensor.state

    @property
    def heater(self) -> 'AqualinkSwitch':
        heater = self.name.lower().replace(' temp', '_heater')
        return self.dev.aqualink._devices[heater]

    @property
    def is_on(self) -> bool:
        return self.heater.state

    def turn_on(self) -> None:
        self.heater.turn_on()

    def turn_off(self) -> None:
        self.heater.turn_off()