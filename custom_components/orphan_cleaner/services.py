"""
Servizi Home Assistant esposti da Orphan Entity Cleaner.

  orphan_cleaner.scan
  orphan_cleaner.delete_orphans
  orphan_cleaner.delete_orphan_devices
"""
from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

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


async def _handle_scan(call: ServiceCall) -> None:
    """
    orphan_cleaner.scan

    Runs a scan and fires `orphan_cleaner_orphans_found` with the result:
    every candidate has a `category` (safe / review / unavailable).
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


async def _handle_delete_orphans(call: ServiceCall) -> None:
    """
    orphan_cleaner.delete_orphans

    Deletes the given entity_ids. Without entity_ids, deletes only the
    candidates in the `safe` category (never review/unavailable ones).
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
        for eid in target_ids:
            _LOGGER.info("  [dry run] %s", eid)
        return

    deleted, failed = await async_delete_entities(hass, target_ids)
    _LOGGER.info("delete_orphans: %d deleted, %d failed", len(deleted), len(failed))
    if failed:
        _LOGGER.warning("Entities not deleted: %s", ", ".join(failed))


async def _handle_delete_orphan_devices(call: ServiceCall) -> None:
    """
    orphan_cleaner.delete_orphan_devices

    Deletes devices with no entities left and no existing config entry.
    Without device_ids, deletes all of them.

    With force (requires device_ids), the listed devices are removed from the
    device registry even if they are not detected as orphans.
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
    if dry_run:
        for did in target:
            _LOGGER.info("  [dry run] %s", did)
        return
    deleted, failed = await async_delete_devices(hass, target, force=force)
    _LOGGER.info("delete_orphan_devices: %d deleted, %d failed", len(deleted), len(failed))
    if failed:
        _LOGGER.warning("Devices not deleted: %s", ", ".join(failed))


def async_register_services(hass: HomeAssistant) -> None:
    """Registra i servizi in Home Assistant."""
    hass.services.async_register(DOMAIN, SERVICE_SCAN, _handle_scan, schema=SCHEMA_SCAN)
    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_ORPHANS, _handle_delete_orphans, schema=SCHEMA_DELETE
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_ORPHAN_DEVICES, _handle_delete_orphan_devices,
        schema=SCHEMA_DELETE_DEVICES,
    )
    _LOGGER.debug("Orphan Cleaner services registered")


def async_unregister_services(hass: HomeAssistant) -> None:
    """Rimuove i servizi quando l'integrazione viene rimossa."""
    for service in (SERVICE_SCAN, SERVICE_DELETE_ORPHANS, SERVICE_DELETE_ORPHAN_DEVICES):
        hass.services.async_remove(DOMAIN, service)
