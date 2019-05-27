"""Support for Aqualink Thermostats."""
import logging
from typing import TYPE_CHECKING, List, Optional

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    DOMAIN, STATE_HEAT, STATE_IDLE, SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_OPERATION_MODE)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ON, STATE_OFF, ATTR_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT)
from homeassistant.helpers.typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['aqualink']

AQUALINK_DOMAIN = 'aqualink'

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
        flags = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE)
        return flags

    @property
    def operation_list(self) -> List[str]:
        return [STATE_HEAT, STATE_OFF]

    @property
    def pump(self) -> 'AqualinkPump':
        pump = self.name.lower() + '_pump'
        return self.dev.system.devices[pump]

    @property
    def current_operation(self) -> str:
        from iaqualink import AqualinkState
        state = AqualinkState(self.heater.state)
        if state == AqualinkState.ON:
            return STATE_HEAT
        elif state == AqualinkState.ENABLED:
            return STATE_IDLE
        else:
            return STATE_OFF

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        if operation_mode == STATE_HEAT:
            await self.async_turn_on()
        elif operation_mode == STATE_OFF:
            await self.async_turn_off()
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

    @property
    def is_on(self) -> bool:
        from iaqualink import AqualinkState
        return self.heater.is_on

    async def async_turn_on(self) -> None:
        await self.heater.turn_on()

    async def async_turn_off(self) -> None:
        await self.heater.turn_off()
