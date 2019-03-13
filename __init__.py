"""Component to embed Aqualink devices."""
import logging

import voluptuous as vol

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_LIGHTS, \
	CONF_SENSORS, CONF_SWITCHES, CONF_DISCOVERY
from homeassistant import config_entries
from homeassistant.helpers import config_entry_flow
import homeassistant.helpers.config_validation as cv


_LOGGER = logging.getLogger(__name__)

DOMAIN = 'aqualink'

ATTR_CONFIG = 'config'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_DISCOVERY, default=True): cv.boolean,
    }),
}, extra=vol.ALLOW_EXTRA)

REQUIREMENTS = ['requests-html==0.10.0']


async def _async_has_devices(hass):
    """Return if there are devices that can be discovered."""
    def discover():
        return True
    return await hass.async_add_executor_job(discover)

async def async_setup(hass, config):
    """Set up the Aqualink component."""
    conf = config.get(DOMAIN)

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][ATTR_CONFIG] = conf

    if conf is not None:
        hass.async_create_task(hass.config_entries.flow.async_init(
            DOMAIN, context={'source': config_entries.SOURCE_IMPORT}))

    return True


async def async_setup_entry(hass, config_entry):
    """Set up Aqualink from a config entry."""
    from .api import Aqualink, AqualinkSensor, AqualinkSwitch, AqualinkLight

    devices = {}

    config_data = hass.data[DOMAIN].get(ATTR_CONFIG)

    username = config_data.get(CONF_USERNAME)
    password = config_data.get(CONF_PASSWORD)

    # These will contain the initialized devices
    lights = hass.data[DOMAIN][CONF_LIGHTS] = []
    sensors = hass.data[DOMAIN][CONF_SENSORS] = []
    switches = hass.data[DOMAIN][CONF_SWITCHES] = []

    # When arriving from configure integrations, we have no config data.
    if config_data is not None:
        aqualink = Aqualink(username, password)
        aqualink.refresh()
        devices = aqualink.get_devices()
        for dev in devices:
            if type(dev) == AqualinkSensor:
                 sensors += [dev]
            elif type(dev) == AqualinkLight:
                 lights += [dev]
            elif type(dev) == AqualinkSwitch:
                 switches += [dev]

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

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    forward_unload = hass.config_entries.async_forward_entry_unload
    remove_lights = remove_switches = False
    if hass.data[DOMAIN][CONF_LIGHTS]:
        remove_lights = await forward_unload(entry, 'light')
    if hass.data[DOMAIN][CONF_SENSORS]:
        remove_sensors = await forward_unload(entry, 'sensor')
    if hass.data[DOMAIN][CONF_SWITCHES]:
        remove_switches = await forward_unload(entry, 'switch')

    if remove_lights or remove_sensors or remove_switches:
        hass.data[DOMAIN].clear()
        return True

    # We were not able to unload the platforms, either because there
    # were none or one of the forward_unloads failed.
    return False

config_entry_flow.register_discovery_flow(DOMAIN,
                                          'Aqualink',
                                          _async_has_devices,
                                          config_entries.CONN_CLASS_LOCAL_POLL) # Not really.
