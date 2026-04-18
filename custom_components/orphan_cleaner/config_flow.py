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


class OrphanCleanerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Gestisce il flusso di configurazione iniziale."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            return self.async_create_entry(
                title="Orphan Entity Cleaner",
                data=user_input,
            )

        schema = vol.Schema({
            vol.Optional(CONF_MIN_AGE_HOURS, default=DEFAULT_MIN_AGE_HOURS):
                vol.All(int, vol.Range(min=1, max=720)),
            vol.Optional(CONF_AGGRESSIVE, default=DEFAULT_AGGRESSIVE): bool,
        })

        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OrphanCleanerOptionsFlow(config_entry)


class OrphanCleanerOptionsFlow(config_entries.OptionsFlow):
    """Gestisce le opzioni modificabili dopo l'installazione."""

    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self._config_entry.data, **self._config_entry.options}

        schema = vol.Schema({
            vol.Optional(CONF_MIN_AGE_HOURS,
                         default=current.get(CONF_MIN_AGE_HOURS, DEFAULT_MIN_AGE_HOURS)):
                vol.All(int, vol.Range(min=1, max=720)),
            vol.Optional(CONF_AGGRESSIVE,
                         default=current.get(CONF_AGGRESSIVE, DEFAULT_AGGRESSIVE)): bool,
        })

        return self.async_show_form(step_id="init", data_schema=schema)
