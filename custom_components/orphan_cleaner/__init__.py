"""
Orphan Entity Cleaner — Custom Integration for Home Assistant.

Detects and removes orphan entities from the HA registry via:
  - Web panel accessible from the sidebar
  - HA services callable from scripts and automations
"""
from __future__ import annotations

import logging
import shutil
import pathlib

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components import frontend

from .const import DOMAIN, PANEL_URL, PANEL_NAME, PANEL_ICON, VERSION
from .panel_api import async_register_views
from .services import async_register_services, async_unregister_services

_LOGGER = logging.getLogger(__name__)

# Must match customElements.define(...) in orphan-cleaner-panel.js
PANEL_ELEMENT_NAME = "orphan-cleaner-panel-" + VERSION.replace(".", "-")


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["config_entry"] = entry

    # Remove __pycache__ to force module reload on update
    _pycache = pathlib.Path(__file__).parent / "__pycache__"
    if _pycache.exists():
        shutil.rmtree(_pycache, ignore_errors=True)

    async_register_views(hass)
    async_register_services(hass)

    frontend.async_register_built_in_panel(
        hass,
        component_name="custom",
        sidebar_title=PANEL_NAME,
        sidebar_icon=PANEL_ICON,
        frontend_url_path=PANEL_URL,
        config={
            "_panel_custom": {
                "name":           PANEL_ELEMENT_NAME,
                "js_url":         f"/api/orphan_cleaner/orphan-cleaner-panel.js?v={VERSION}",
                "embed_iframe":   False,
                "trust_external": False,
            }
        },
        require_admin=True,
    )

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    _LOGGER.info("Orphan Entity Cleaner %s loaded", VERSION)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    async_unregister_services(hass)
    frontend.async_remove_panel(hass, PANEL_URL)
    hass.data[DOMAIN].pop("config_entry", None)
    _LOGGER.info("Orphan Entity Cleaner %s unloaded", VERSION)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
