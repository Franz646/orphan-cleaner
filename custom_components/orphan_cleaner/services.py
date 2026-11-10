"""
Servizi Home Assistant esposti da Orphan Entity Cleaner.

  orphan_cleaner.scan
  orphan_cleaner.delete_orphans
  orphan_cleaner.delete_orphan_devices
"""
from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service

from .const import (
    DOMAIN,
    CONF_MIN_AGE_HOURS,
    CONF_AGGRESSIVE,
    DEFAULT_MIN_AGE_HOURS,
    DEFAULT_AGGRESSIVE,
    SERVICE_SCAN,
    SERVICE_DELETE_ORPHANS,
    SERVICE_DELETE_ORPHAN_DEVICES,
    FIELD_ENTITY_IDS,
    FIELD_DEVICE_IDS,
    FIELD_DRY_RUN,
    FIELD_FORCE,
    EVENT_ORPHANS_FOUND,
)
from .orphan_detector import (
    CATEGORY_SAFE,
    detect_orphans,
    detect_orphan_devices,
    async_delete_entities,
    async_delete_devices,
    describe_device_removal,
    startup_grace_active,
)

_LOGGER = logging.getLogger(__name__)

SCHEMA_SCAN = vol.Schema({})

SCHEMA_DELETE = vol.Schema(
    {
        vol.Optional(FIELD_ENTITY_IDS): vol.All(cv.ensure_list, [cv.entity_id]),
        vol.Optional(FIELD_DRY_RUN, default=False): cv.boolean,
    }
)

SCHEMA_DELETE_DEVICES = vol.Schema(
    {
        vol.Optional(FIELD_DEVICE_IDS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(FIELD_DRY_RUN, default=False): cv.boolean,
        vol.Optional(FIELD_FORCE, default=False): cv.boolean,
    }
)


def _get_config(hass: HomeAssistant) -> dict:
    """Legge min_age e aggressive dalla config entry attiva."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        return {}
    e = entries[0]
    return {**e.data, **e.options}


def _scan(hass: HomeAssistant):
    cfg = _get_config(hass)
    return detect_orphans(
        hass,
        min_age_hours=cfg.get(CONF_MIN_AGE_HOURS, DEFAULT_MIN_AGE_HOURS),
        aggressive=cfg.get(CONF_AGGRESSIVE, DEFAULT_AGGRESSIVE),
    )


async def _handle_scan(call: ServiceCall) -> ServiceResponse:
    """
    orphan_cleaner.scan

    Runs a scan and fires `orphan_cleaner_orphans_found` with the result:
    every candidate has a `category` (safe / review / unavailable).
    The same payload is returned as the service response.
    """
    hass    = call.hass
    orphans = _scan(hass)
    payload = {
        "count":          len(orphans),
        "count_safe":     sum(1 for o in orphans if o.category == CATEGORY_SAFE),
        "orphans":        [o.as_dict() for o in orphans],
        "orphan_devices": detect_orphan_devices(hass),
        "startup_grace":  startup_grace_active(hass),
    }
    hass.bus.async_fire(EVENT_ORPHANS_FOUND, payload)
    _LOGGER.info(
        "Service scan: %d candidates (%d safe) - event '%s' fired",
        payload["count"], payload["count_safe"], EVENT_ORPHANS_FOUND,
    )
    return payload


async def _handle_delete_orphans(call: ServiceCall) -> ServiceResponse:
    """
    orphan_cleaner.delete_orphans

    Deletes the given entity_ids. Without entity_ids, deletes only the
    candidates in the `safe` category (never review/unavailable ones).
    Returns what was (or, with dry_run, would be) deleted.
    """
    hass      = call.hass
    dry_run   = call.data.get(FIELD_DRY_RUN, False)
    ids_input = call.data.get(FIELD_ENTITY_IDS)

    if ids_input:
        target_ids = ids_input
    else:
        target_ids = [o.entity_id for o in _scan(hass) if o.category == CATEGORY_SAFE]

    _LOGGER.info("Service delete_orphans: %d entities to delete (dry_run=%s)",
                 len(target_ids), dry_run)
    if dry_run:
        # Warning, not info: the default log level hides info, and a dry run
        # that shows nothing is useless.
        _LOGGER.warning(
            "[dry run] delete_orphans would delete %d entities: %s",
            len(target_ids), ", ".join(target_ids) or "none",
        )
        return {"dry_run": True, "would_delete": list(target_ids)}

    deleted, failed = await async_delete_entities(hass, target_ids)
    _LOGGER.info("delete_orphans: %d deleted, %d failed", len(deleted), len(failed))
    if failed:
        _LOGGER.warning("Entities not deleted: %s", ", ".join(failed))
    return {"dry_run": False, "deleted": list(deleted), "failed": list(failed)}


def _log_force_removal(hass: HomeAssistant, device_ids: list[str], dry_run: bool) -> None:
    """Logga cosa elimina force, come warning perché sia visibile con i log predefiniti."""
    action = "[dry run] force would remove" if dry_run else "Force removing"
    for did in device_ids:
        info = describe_device_removal(hass, did)
        if info is None:
            _LOGGER.warning("%s device %s: not found in the device registry", action, did)
            continue
        _LOGGER.warning(
            "%s device %s (%s) and its %d entities: %s",
            action, info["name"], did, len(info["entities"]),
            ", ".join(info["entities"]) or "none",
        )
        for eid, refs in info["used_in"].items():
            _LOGGER.warning("  %s is still used by: %s", eid, ", ".join(refs))


async def _handle_delete_orphan_devices(call: ServiceCall) -> ServiceResponse:
    """
    orphan_cleaner.delete_orphan_devices

    Deletes devices with no entities left and no existing config entry.
    Without device_ids, deletes all of them.

    With force (requires device_ids), the listed devices are removed from the
    device registry even if they are not detected as orphans.
    Returns what was (or, with dry_run, would be) deleted.
    """
    hass      = call.hass
    dry_run   = call.data.get(FIELD_DRY_RUN, False)
    force     = call.data.get(FIELD_FORCE, False)
    ids_input = call.data.get(FIELD_DEVICE_IDS)

    if force and not ids_input:
        raise ServiceValidationError("force requires an explicit list of device_ids")

    target = ids_input or [d["device_id"] for d in detect_orphan_devices(hass)]

    _LOGGER.info("Service delete_orphan_devices: %d devices (dry_run=%s, force=%s)",
                 len(target), dry_run, force)
    if force:
        _log_force_removal(hass, target, dry_run)
    if dry_run:
        _LOGGER.warning(
            "[dry run] delete_orphan_devices would delete %d devices: %s",
            len(target), ", ".join(target) or "none",
        )
        response: dict = {"dry_run": True, "force": force, "would_delete": list(target)}
        if force:
            response["details"] = {
                did: describe_device_removal(hass, did) for did in target
            }
        return response
    deleted, failed = await async_delete_devices(hass, target, force=force)
    _LOGGER.info("delete_orphan_devices: %d deleted, %d failed", len(deleted), len(failed))
    if failed:
        _LOGGER.warning("Devices not deleted: %s", ", ".join(failed))
    return {"dry_run": False, "force": force, "deleted": list(deleted), "failed": list(failed)}


def _register(hass: HomeAssistant, service: str, handler, schema) -> None:
    """Registra un servizio admin con risposta opzionale.

    async_register_admin_service accetta supports_response solo da HA 2025.6:
    sulle versioni precedenti il servizio viene registrato senza risposta
    (i risultati restano nel log e nell'evento).
    """
    try:
        async_register_admin_service(
            hass, DOMAIN, service, handler, schema=schema,
            supports_response=SupportsResponse.OPTIONAL,
        )
    except TypeError:
        async_register_admin_service(hass, DOMAIN, service, handler, schema=schema)


def async_register_services(hass: HomeAssistant) -> None:
    """Registra i servizi in Home Assistant (solo admin)."""
    _register(hass, SERVICE_SCAN, _handle_scan, SCHEMA_SCAN)
    _register(hass, SERVICE_DELETE_ORPHANS, _handle_delete_orphans, SCHEMA_DELETE)
    _register(
        hass, SERVICE_DELETE_ORPHAN_DEVICES, _handle_delete_orphan_devices,
        SCHEMA_DELETE_DEVICES,
    )
    _LOGGER.debug("Orphan Cleaner services registered")


def async_unregister_services(hass: HomeAssistant) -> None:
    """Rimuove i servizi quando l'integrazione viene rimossa."""
    for service in (SERVICE_SCAN, SERVICE_DELETE_ORPHANS, SERVICE_DELETE_ORPHAN_DEVICES):
        hass.services.async_remove(DOMAIN, service)
