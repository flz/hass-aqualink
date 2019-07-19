"""Support for Aqualink Thermostats."""
import logging
from typing import TYPE_CHECKING, List, Optional

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    DOMAIN, HVAC_MODE_HEAT, HVAC_MODE_OFF, SUPPORT_TARGET_TEMPERATURE)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT)
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN as AQUALINK_DOMAIN

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

if TYPE_CHECKING:
    from iaqualink import (
        AqualinkHeater, AqualinkPump, AqualinkSensor, AqualinkState,
        AqualinkThermostat)


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
        return self.dev.label.split(' ')[0]

    async def async_update(self) -> None:
        """Get the latest state from the thermostat."""
        # Only update if this is the main thermostat.
        if self.name != 'Pool':
            return None
        # ... otherwise, disable since throttling on the API side doesn't work.
        await self.dev.system.update()

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        flags = (SUPPORT_TARGET_TEMPERATURE)
        return flags

    @property
    def hvac_modes(self) -> List[str]:
        return [HVAC_MODE_HEAT, HVAC_MODE_OFF]

    @property
    def pump(self) -> 'AqualinkPump':
        pump = self.name.lower() + '_pump'
        return self.dev.system.devices[pump]

    @property
    def hvac_mode(self) -> str:
        from iaqualink import AqualinkState
        state = AqualinkState(self.heater.state)
        if state == AqualinkState.ON:
            return HVAC_MODE_HEAT
        else:
            return HVAC_MODE_OFF

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        if hvac_mode == HVAC_MODE_HEAT:
            await self.heater.turn_on()
        elif hvac_mode == HVAC_MODE_OFF:
            await self.heater.turn_off()
        else:
            _LOGGER.warning(f"Unknown operation mode: {operation_mode}")

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        if self.dev.system.temp_unit == "F":
            return TEMP_FAHRENHEIT
        else:
            return TEMP_CELSIUS

    @property
    def min_temp(self) -> int:
        from iaqualink.const import (
            AQUALINK_TEMP_CELSIUS_LOW,
            AQUALINK_TEMP_FAHRENHEIT_LOW,
        )

        if self.temperature_unit == TEMP_FAHRENHEIT:
            return AQUALINK_TEMP_FAHRENHEIT_LOW
        else:
            return AQUALINK_TEMP_CELSIUS_LOW

    @property
    def max_temp(self) -> int:
        from iaqualink.const import (
            AQUALINK_TEMP_CELSIUS_HIGH,
            AQUALINK_TEMP_FAHRENHEIT_HIGH,
        )

        if self.temperature_unit == TEMP_FAHRENHEIT:
            return AQUALINK_TEMP_FAHRENHEIT_HIGH
        else:
            return AQUALINK_TEMP_CELSIUS_HIGH

    @property
    def target_temperature(self) -> int:
        return int(self.dev.state)

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        await self.dev.set_temperature(int(kwargs[ATTR_TEMPERATURE]))

    @property
    def sensor(self) -> 'AqualinkSensor':
        sensor = self.name.lower() + '_temp'
        return self.dev.system.devices[sensor]

    @property
    def current_temperature(self) -> Optional[int]:
        """Return the current temperature."""
        return int(self.sensor.state) if self.sensor.state else None

    @property
    def heater(self) -> 'AqualinkHeater':
        heater = self.name.lower() + '_heater'
        return self.dev.system.devices[heater]
