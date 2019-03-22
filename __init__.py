"""Component to embed Aqualink devices."""
import logging
from typing import Any, Dict

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_LIGHTS, \
    CONF_SENSORS, CONF_SWITCHES, CONF_DISCOVERY
from homeassistant.helpers import config_entry_flow
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['requests-html==0.10.0']

ATTR_CONFIG = 'config'
CONF_CLIMATES = 'climate'
DOMAIN = 'aqualink'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_DISCOVERY, default=True): cv.boolean,
    }),
}, extra=vol.ALLOW_EXTRA)


async def _async_has_devices(hass: HomeAssistantType) -> bool:
    """Return if there are devices that can be discovered."""
    def discover():
        return True
    return await hass.async_add_executor_job(discover)

async def async_setup(hass: HomeAssistantType,
                      config: Dict[str, Any]) -> None:
    """Set up the Aqualink component."""
    conf = config.get(DOMAIN)

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][ATTR_CONFIG] = conf

    if conf is not None:
        hass.async_create_task(hass.config_entries.flow.async_init(
            DOMAIN, context={'source': config_entries.SOURCE_IMPORT}))

    return True

async def async_setup_entry(hass: HomeAssistantType,
                            config_entry: ConfigEntry) -> None:
    """Set up Aqualink from a config entry."""
    from .api import (
        Aqualink, AqualinkSensor, AqualinkSwitch, AqualinkLight,
        AqualinkThermostat)

    config_data = hass.data[DOMAIN].get(ATTR_CONFIG)

    username = config_data.get(CONF_USERNAME)
    password = config_data.get(CONF_PASSWORD)

    # These will contain the initialized devices
    lights = hass.data[DOMAIN][CONF_LIGHTS] = []
    sensors = hass.data[DOMAIN][CONF_SENSORS] = []
    switches = hass.data[DOMAIN][CONF_SWITCHES] = []
    climates = hass.data[DOMAIN][CONF_CLIMATES] = []

    # When arriving from configure integrations, we have no config data.
    if config_data is not None:
        aqualink = Aqualink(username, password)
        aqualink.refresh()
        for dev in aqualink.devices:
            if type(dev) == AqualinkSensor:
                 sensors += [dev]
            elif type(dev) == AqualinkLight:
                 lights += [dev]
            elif type(dev) == AqualinkSwitch:
                 switches += [dev]
            elif type(dev) == AqualinkThermostat:
                 climates += [dev]

    forward_setup = hass.config_entries.async_forward_entry_setup
    if lights:
        _LOGGER.debug("Got %s lights: %s", len(lights), lights)
        hass.async_create_task(forward_setup(config_entry, 'light'))
    if sensors:
        _LOGGER.debug("Got %s sensors: %s", len(sensors), sensors)
        hass.async_create_task(forward_setup(config_entry, 'sensor'))
    if switches:
        _LOGGER.debug("Got %s switches: %s", len(switches), switches)
        hass.async_create_task(forward_setup(config_entry, 'switch'))
    if climates:
        _LOGGER.debug("Got %s climates: %s", len(climates), climates)
        hass.async_create_task(forward_setup(config_entry, 'climate'))


async def async_unload_entry(hass: HomeAssistantType,
                             entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    forward_unload = hass.config_entries.async_forward_entry_unload
    remove_lights = remove_switches = False
    if hass.data[DOMAIN][CONF_LIGHTS]:
        remove_lights = await forward_unload(entry, 'light')
    if hass.data[DOMAIN][CONF_SENSORS]:
        remove_sensors = await forward_unload(entry, 'sensor')
    if hass.data[DOMAIN][CONF_SWITCHES]:
        remove_switches = await forward_unload(entry, 'switch')
    if hass.data[DOMAIN][CONF_CLIMATES]:
        remove_climates = await forward_unload(entry, 'climate')

    if remove_lights or remove_sensors or remove_switches or remove_climates:
        hass.data[DOMAIN].clear()
        return True

    # We were not able to unload the platforms, either because there
    # were none or one of the forward_unloads failed.
    return False

config_entry_flow.register_discovery_flow(DOMAIN,
                                          'Aqualink',
                                          _async_has_devices,
                                          config_entries.CONN_CLASS_LOCAL_POLL) # Not really.
