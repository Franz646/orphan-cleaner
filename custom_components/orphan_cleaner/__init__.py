"""
Orphan Entity Cleaner — Custom Integration per Home Assistant.

Rileva ed elimina le entità orfane dal registro di HA tramite:
  • Panel web accessibile dalla barra laterale
  • Servizi HA richiamabili da script e automazioni
"""
from __future__ import annotations

import logging
import shutil
import pathlib

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components import frontend

from .const import DOMAIN, PANEL_URL, PANEL_NAME, PANEL_ICON
from .panel_api import async_register_views
from .services import async_register_services, async_unregister_services

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Chiamata da HA all'avvio — non configurabile da YAML."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Chiamata quando l'utente aggiunge l'integrazione dal UI.
    Registra le view HTTP, i servizi e il panel nella sidebar.
    """
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["config_entry"] = entry

    # Rimuove __pycache__ per forzare ricaricamento moduli aggiornati
    _pycache = pathlib.Path(__file__).parent / "__pycache__"
    if _pycache.exists():
        shutil.rmtree(_pycache, ignore_errors=True)
        _LOGGER.debug("__pycache__ rimossa")

    # ── View HTTP (panel + API REST interna) ───────────────────────────
    async_register_views(hass)

    # ── Servizi HA ─────────────────────────────────────────────────────
    async_register_services(hass)

    # ── Panel nella sidebar ────────────────────────────────────────────
    frontend.async_register_built_in_panel(
        hass,
        component_name="custom",
        sidebar_title=PANEL_NAME,
        sidebar_icon=PANEL_ICON,
        frontend_url_path=PANEL_URL,
        config={
            "_panel_custom": {
                "name":          "orphan-cleaner-panel",
                "js_url": "/api/orphan_cleaner/orphan-cleaner-panel.js?v=1.0.4",
                "embed_iframe":  False,
                "trust_external": False,
            }
        },
        require_admin=True,
    )

    # Ascolta aggiornamenti delle opzioni (cambia min_age o aggressive)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    _LOGGER.info("Orphan Entity Cleaner caricato correttamente")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Pulizia quando l'integrazione viene rimossa."""
    async_unregister_services(hass)

    frontend.async_remove_panel(hass, PANEL_URL)

    hass.data[DOMAIN].pop("config_entry", None)
    _LOGGER.info("Orphan Entity Cleaner rimosso")
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Ricarica l'entry quando le opzioni vengono modificate."""
    await hass.config_entries.async_reload(entry.entry_id)
