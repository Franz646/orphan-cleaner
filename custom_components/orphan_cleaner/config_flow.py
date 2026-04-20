"""Config flow per Orphan Entity Cleaner."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    DOMAIN,
    CONF_MIN_AGE_HOURS,
    CONF_AGGRESSIVE,
    DEFAULT_MIN_AGE_HOURS,
    DEFAULT_AGGRESSIVE,
)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MIN_AGE_HOURS, default=DEFAULT_MIN_AGE_HOURS): vol.All(
            int, vol.Range(min=1, max=720)
        ),
        vol.Required(CONF_AGGRESSIVE, default=DEFAULT_AGGRESSIVE): bool,
    }
)


class OrphanCleanerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Gestisce il config flow dell'integrazione."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Step iniziale mostrato all'utente."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            return self.async_create_entry(
                title="Orphan Entity Cleaner",
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OrphanCleanerOptionsFlow(config_entry)


class OrphanCleanerOptionsFlow(config_entries.OptionsFlow):
    """Gestisce le opzioni modificabili dopo l'installazione."""

    def __init__(self, config_entry):
        self._entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_MIN_AGE_HOURS,
                    default=self._entry.options.get(
                        CONF_MIN_AGE_HOURS,
                        self._entry.data.get(CONF_MIN_AGE_HOURS, DEFAULT_MIN_AGE_HOURS),
                    ),
                ): vol.All(int, vol.Range(min=1, max=720)),
                vol.Required(
                    CONF_AGGRESSIVE,
                    default=self._entry.options.get(
                        CONF_AGGRESSIVE,
                        self._entry.data.get(CONF_AGGRESSIVE, DEFAULT_AGGRESSIVE),
                    ),
                ): bool,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
