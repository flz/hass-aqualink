"""Component to embed Aqualink devices."""
from aiohttp import CookieJar
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_LIGHTS, \
    CONF_SENSORS, CONF_SWITCHES, CONF_DISCOVERY
from homeassistant.helpers import config_entry_flow
from homeassistant.helpers.aiohttp_client import async_create_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import (
    ConfigType, HomeAssistantType)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['iaqualink==0.2.7']

ATTR_CONFIG = 'config'
CONF_CLIMATES = 'climate'
PARALLEL_UPDATES = 0

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistantType,
                      config: ConfigType) -> None:
    """Set up the Aqualink component."""
    conf = config.get(DOMAIN)

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][ATTR_CONFIG] = conf

    if conf is not None:
        hass.async_create_task(hass.config_entries.flow.async_init(
            DOMAIN, context={'source': config_entries.SOURCE_IMPORT},
            data=conf))

    return True

async def async_setup_entry(hass: HomeAssistantType,
                            entry: ConfigEntry) -> None:
    """Set up Aqualink from a config entry."""
    from iaqualink import (
        AqualinkClient, AqualinkLight, AqualinkSensor, AqualinkSystem,
        AqualinkToggle, AqualinkThermostat)

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    # These will contain the initialized devices
    climates = hass.data[DOMAIN][CLIMATE_DOMAIN] = []
    lights = hass.data[DOMAIN][LIGHT_DOMAIN] = []
    sensors = hass.data[DOMAIN][SENSOR_DOMAIN] = []
    switches = hass.data[DOMAIN][SWITCH_DOMAIN] = []

    session = async_create_clientsession(hass, cookie_jar=CookieJar(unsafe=True))
    aqualink = AqualinkClient(username, password, session)
    try:
        await aqualink.login()
    except Exception as e:
        _LOGGER.error(f'Exception raised while attempting to login: {e}')
        return False

    systems = await aqualink.get_systems()
    systems = list(systems.values())
    if len(systems) == 0:
        _LOGGER.error("No systems detected or supported.")
        return False

    # Only supporting the first system for now.
    devices = await systems[0].get_devices()

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
    if climates:
        _LOGGER.debug("Got %s climates: %s", len(climates), climates)
        hass.async_create_task(forward_setup(entry, CLIMATE_DOMAIN))
    if lights:
        _LOGGER.debug("Got %s lights: %s", len(lights), lights)
        hass.async_create_task(forward_setup(entry, LIGHT_DOMAIN))
    if sensors:
        _LOGGER.debug("Got %s sensors: %s", len(sensors), sensors)
        hass.async_create_task(forward_setup(entry, SENSOR_DOMAIN))
    if switches:
        _LOGGER.debug("Got %s switches: %s", len(switches), switches)
        hass.async_create_task(forward_setup(entry, SWITCH_DOMAIN))

    return True


async def async_unload_entry(hass: HomeAssistantType,
                             entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    remove_climates = remove_lights = remove_sensors = remove_switches = False

    forward_unload = hass.config_entries.async_forward_entry_unload
    if hass.data[DOMAIN][CLIMATE_DOMAIN]:
        remove_climates = await forward_unload(entry, CLIMATE_DOMAIN)
    if hass.data[DOMAIN][LIGHT_DOMAIN]:
        remove_lights = await forward_unload(entry, LIGHT_DOMAIN)
    if hass.data[DOMAIN][SENSOR_DOMAIN]:
        remove_sensors = await forward_unload(entry, SENSOR_DOMAIN)
    if hass.data[DOMAIN][SWITCH_DOMAIN]:
        remove_switches = await forward_unload(entry, SWITCH_DOMAIN)

    hass.data[DOMAIN].clear()

    return (remove_climates and remove_lights and remove_sensors and
            remove_switches)
