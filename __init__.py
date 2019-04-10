"""Component to embed Aqualink devices."""
from aiohttp import CookieJar
import logging
from typing import Any, Dict

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_LIGHTS, \
    CONF_SENSORS, CONF_SWITCHES, CONF_DISCOVERY
from homeassistant.helpers import config_entry_flow
from homeassistant.helpers.aiohttp_client import async_create_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['aiohttp==3.5.4', 'requests-html==0.10.0']

ATTR_CONFIG = 'config'
CONF_CLIMATES = 'climate'
DOMAIN = 'aqualink'
PARALLEL_UPDATES = 0

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
        Aqualink, AqualinkLight, AqualinkSensor, AqualinkSystem,
        AqualinkToggle, AqualinkThermostat)

    config_data = hass.data[DOMAIN].get(ATTR_CONFIG)

    username = config_data.get(CONF_USERNAME)
    password = config_data.get(CONF_PASSWORD)

    # These will contain the initialized devices
    lights = hass.data[DOMAIN][CONF_LIGHTS] = []
    sensors = hass.data[DOMAIN][CONF_SENSORS] = []
    switches = hass.data[DOMAIN][CONF_SWITCHES] = []
    climates = hass.data[DOMAIN][CONF_CLIMATES] = []

    hass.loop.set_debug(True)

    # When arriving from configure integrations, we have no config data.
    if config_data is not None:
        session = async_create_clientsession(hass, cookie_jar=CookieJar(unsafe=True))
        aqualink = Aqualink(username, password, session)
        try:
            await aqualink.login()
        except Exception as e:
            _LOGGER.error(f'Exception raised while attempting to login: {e}')
            return False

        systems = await aqualink.get_systems()
        pool = AqualinkSystem(aqualink, systems[0]['serial_number'])
        devices = await pool.get_devices()

        for dev in devices.values():
            if isinstance(dev, AqualinkSensor):
                 sensors += [dev]
            elif isinstance(dev, AqualinkLight):
                 lights += [dev]
            elif isinstance(dev, AqualinkToggle):
                 switches += [dev]
            elif isinstance(dev, AqualinkThermostat):
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

    return True


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
                                          config_entries.CONN_CLASS_CLOUD_POLL) # Not really.
