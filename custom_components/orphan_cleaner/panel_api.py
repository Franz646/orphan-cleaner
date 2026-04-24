"""
Endpoint HTTP per il panel web di Orphan Entity Cleaner.
Registra una view aiohttp direttamente nel server HTTP di Home Assistant.
"""
from __future__ import annotations

import json
import logging
import pathlib

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_MIN_AGE_HOURS, CONF_AGGRESSIVE, DEFAULT_MIN_AGE_HOURS, DEFAULT_AGGRESSIVE
from .orphan_detector import detect_orphans, async_delete_entities

_LOGGER = logging.getLogger(__name__)

FRONTEND_DIR = pathlib.Path(__file__).parent / "frontend"


class OrphanCleanerIndexView(HomeAssistantView):
    """Serve la pagina HTML del panel."""

    url          = "/api/orphan_cleaner/panel"
    name         = "api:orphan_cleaner:panel"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        html = await request.loop.run_in_executor(
            None, (FRONTEND_DIR / "panel.html").read_text, "utf-8"
        )
        return web.Response(content_type="text/html", text=html)


class OrphanCleanerScanView(HomeAssistantView):
    """Endpoint GET /api/orphan_cleaner/scan — restituisce le entità orfane in JSON."""

    url          = "/api/orphan_cleaner/scan"
    name         = "api:orphan_cleaner:scan"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]

        entry  = _get_config_entry(hass)
        config = {**entry.data, **entry.options} if entry else {}

        min_age    = int(request.rel_url.query.get("min_age", config.get(CONF_MIN_AGE_HOURS, DEFAULT_MIN_AGE_HOURS)))

        try:
            from homeassistant.helpers import entity_registry as er
            registry = er.async_get(hass)
            total    = len(registry.entities)
            # Always scan with aggressive=True — client filters by method
            orphans  = detect_orphans(hass, min_age_hours=min_age, aggressive=True)

            return web.Response(
                content_type="application/json",
                text=json.dumps({
                    "total":      total,
                    "orphans":    [o.as_dict() for o in orphans],
                    "min_age":    min_age,
                    "aggressive": aggressive,
                    "error":      None,
                }),
            )
        except Exception as exc:
            _LOGGER.exception("Errore scansione API")
            return web.Response(
                status=500,
                content_type="application/json",
                text=json.dumps({"error": str(exc), "orphans": [], "total": 0}),
            )


class OrphanCleanerDeleteView(HomeAssistantView):
    """Endpoint POST /api/orphan_cleaner/delete — elimina le entità specificate."""

    url          = "/api/orphan_cleaner/delete"
    name         = "api:orphan_cleaner:delete"
    requires_auth = False

    async def post(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]

        try:
            body = await request.json()
        except Exception:
            return web.Response(status=400, text='{"error":"JSON non valido"}',
                                content_type="application/json")

        entity_ids = body.get("entity_ids", [])
        if not entity_ids:
            return web.Response(status=400,
                                text='{"error":"entity_ids mancante o vuoto"}',
                                content_type="application/json")

        try:
            deleted, failed = await async_delete_entities(hass, entity_ids)
            return web.Response(
                content_type="application/json",
                text=json.dumps({
                    "deleted":       deleted,
                    "failed":        failed,
                    "deleted_count": len(deleted),
                    "failed_count":  len(failed),
                }),
            )
        except Exception as exc:
            _LOGGER.exception("Errore delete API")
            return web.Response(
                status=500,
                content_type="application/json",
                text=json.dumps({"error": str(exc)}),
            )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _get_config_entry(hass: HomeAssistant):
    """Recupera la prima config entry dell'integrazione."""
    entries = hass.config_entries.async_entries(DOMAIN)
    return entries[0] if entries else None



class OrphanCleanerJsView(HomeAssistantView):
    """Serve il file JavaScript del custom panel."""

    url           = "/api/orphan_cleaner/orphan-cleaner-panel.js"
    name          = "api:orphan_cleaner:js"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        js_path = FRONTEND_DIR / "orphan-cleaner-panel.js"
        if not js_path.exists():
            raise web.HTTPNotFound()
        data = await request.loop.run_in_executor(None, js_path.read_bytes)
        return web.Response(
            body=data,
            content_type="application/javascript",
            headers={"Cache-Control": "no-cache"},
        )


def async_register_views(hass: HomeAssistant) -> None:
    """Registra tutte le view HTTP nel server di HA."""
    hass.http.register_view(OrphanCleanerIconView())
    hass.http.register_view(OrphanCleanerJsView())
    hass.http.register_view(OrphanCleanerIndexView())
    hass.http.register_view(OrphanCleanerScanView())
    hass.http.register_view(OrphanCleanerDeleteView())
    _LOGGER.debug("View HTTP Orphan Cleaner registrate")


IMAGES_DIR = pathlib.Path(__file__).parent / "images"


class OrphanCleanerIconView(HomeAssistantView):
    """Serve l'icona PNG dell'integrazione."""

    url           = "/api/orphan_cleaner/icon.png"
    name          = "api:orphan_cleaner:icon"
    requires_auth = False   # deve essere pubblica per il frontend HA

    async def get(self, request: web.Request) -> web.Response:
        icon_path = IMAGES_DIR / "icon.png"
        if not icon_path.exists():
            raise web.HTTPNotFound()
        data = await request.loop.run_in_executor(None, icon_path.read_bytes)
        return web.Response(
            body=data,
            content_type="image/png",
            headers={"Cache-Control": "public, max-age=86400"},
        )
