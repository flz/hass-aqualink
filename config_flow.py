"""Config flow to configure zone component."""

from typing import Optional
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD)
from homeassistant.helpers import ConfigType
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN


@config_entries.HANDLERS.register(DOMAIN)
class AqualinkFlowHandler(config_entries.ConfigFlow):
    """Aqualink config flow."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input: Optional[ConfigType] = None):
        """Handle a flow start."""
        from iaqualink import AqualinkClient

        errors = {}

        if user_input is not None:
            # Supporting a single account.
            entries = self.hass.config_entries.async_entries(DOMAIN)
            if entries:
                return self.async_abort(reason='already_setup')

            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            try:
                aqualink = AqualinkClient(username, password)
                await aqualink.login()
                return await self.async_step_import(user_input)
            except Exception:
                errors['base'] = 'connection_failure'

        return self.async_show_form(
            step_id='user',
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )

    async def async_step_import(self, user_input: Optional[ConfigType] = None):
        """Occurs when an entry is setup through config."""
        entries = self.hass.config_entries.async_entries(DOMAIN)
        if entries:
            return self.async_abort(reason='already_setup')

        username = user_input[CONF_USERNAME]

        return self.async_create_entry(
            title=username,
            data=user_input)
