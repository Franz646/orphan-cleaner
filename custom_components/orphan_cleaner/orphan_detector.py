"""
Orphan entity detection logic.

Every candidate gets a *category* that tells how safe it is to delete it:

  safe         The entity is no longer provided by anything: Home Assistant
               restored it from the registry (state attribute ``restored``)
               while its integration is loaded, or its config entry no longer
               exists. Deleting it is permanent and loses nothing.
  review       Its integration is disabled, failing or retrying, or it was
               found by the heuristic. It may come back on its own: check
               before deleting.
  unavailable  The integration still provides the entity, but the entity has
               been unavailable for at least ``min_age_hours`` (device off or
               unreachable). Deleting it only lasts until the next reload.

Only the ``safe`` category is included when deleting "all orphans".
"""
from __future__ import annotations

import fnmatch
import logging
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, MANUAL_PLATFORMS, STARTUP_GRACE_SECONDS

_LOGGER = logging.getLogger(__name__)

# Platforms whose entities are legitimately "unavailable" by design
ALWAYS_UNAVAILABLE_PLATFORMS = {
    "template", "group", "universal", "input_boolean",
}

CATEGORY_SAFE        = "safe"
CATEGORY_REVIEW      = "review"
CATEGORY_UNAVAILABLE = "unavailable"

# Config entry states that do not mean "gone": the integration may recover
_ENTRY_STATE_REASON = {
    ConfigEntryState.NOT_LOADED:      "integration not loaded (disabled?)",
    ConfigEntryState.SETUP_ERROR:     "integration failed to set up",
    ConfigEntryState.SETUP_RETRY:     "integration is retrying setup (device or service unreachable)",
    ConfigEntryState.FAILED_UNLOAD:   "integration failed to unload",
    ConfigEntryState.MIGRATION_ERROR: "integration migration error",
}


@dataclass
class OrphanInfo:
    entity_id:   str
    platform:    str
    method:      str
    category:    str
    reason:      str
    age_hours:   float | None
    disabled_by: str | None
    state:       str | None = None
    used_in:     list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


def startup_grace_active(hass: HomeAssistant) -> bool:
    """True right after start-up, when integrations may still be loading."""
    started = hass.data.get(DOMAIN, {}).get("started_at")
    return started is None or (time.monotonic() - started) < STARTUP_GRACE_SECONDS


def _references(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Automations, scripts and scenes that still use the entity."""
    refs: list[str] = []
    finders = []
    try:
        from homeassistant.components.automation import automations_with_entity
        finders.append(automations_with_entity)
    except ImportError:  # pragma: no cover
        pass
    try:
        from homeassistant.components.script import scripts_with_entity
        finders.append(scripts_with_entity)
    except ImportError:  # pragma: no cover
        pass
    try:
        from homeassistant.components.scene import scenes_with_entity
        finders.append(scenes_with_entity)
    except ImportError:  # pragma: no cover
        pass
    for finder in finders:
        try:
            refs.extend(finder(hass, entity_id))
        except Exception:  # integration not loaded or API changed
            continue
    return sorted(set(r for r in refs if r != entity_id))


def detect_orphans(
    hass: HomeAssistant,
    min_age_hours: int = 24,
    aggressive: bool = False,
    ignore_platforms: set[str] | None = None,
    ignore_globs: list[str] | None = None,
) -> list[OrphanInfo]:

    entity_registry = er.async_get(hass)
    now             = datetime.now(timezone.utc)
    grace           = startup_grace_active(hass)
    orphans: list[OrphanInfo] = []
    _ignore         = ignore_platforms or set()
    _globs          = ignore_globs or []

    def _is_ignored(entity_id: str, platform: str) -> bool:
        if platform and platform in _ignore:
            return True
        for pattern in _globs:
            if (fnmatch.fnmatch(entity_id, pattern)
                    or fnmatch.fnmatch(platform, pattern)
                    or platform == pattern):
                return True
        return False

    def _add(entry, method, category, reason, age_h=None, state=None) -> None:
        orphans.append(OrphanInfo(
            entity_id=entry.entity_id, platform=entry.platform or "-",
            method=method, category=category, reason=reason,
            age_hours=None if age_h is None else round(age_h, 1),
            disabled_by=entry.disabled_by, state=state,
            used_in=_references(hass, entry.entity_id),
        ))

    for entry in entity_registry.entities.values():
        platform     = entry.platform or ""
        cfg_entry_id = entry.config_entry_id

        if _is_ignored(entry.entity_id, platform):
            continue

        cfg_obj   = hass.config_entries.async_get_entry(cfg_entry_id) if cfg_entry_id else None
        state_obj = hass.states.get(entry.entity_id)
        restored  = bool(state_obj and state_obj.attributes.get("restored"))

        # 1. Config entry deleted: nothing will ever provide this entity again
        if cfg_entry_id and cfg_obj is None:
            _add(entry, "dead_entry", CATEGORY_SAFE, "its integration was removed")
            continue

        # 2. Config entry present but not running: may come back, review it
        if cfg_obj is not None and cfg_obj.state in _ENTRY_STATE_REASON:
            reason = _ENTRY_STATE_REASON[cfg_obj.state]
            if cfg_obj.disabled_by:
                reason = "integration disabled by " + str(cfg_obj.disabled_by)
            _add(entry, "dead_entry", CATEGORY_REVIEW, reason)
            continue

        # 3. Restored entity: registered, but no longer provided by its source.
        #    Skipped right after start-up, while integrations are still loading.
        if restored and not grace and entry.disabled_by is None:
            if cfg_obj is not None:
                reason = "no longer provided by its integration"
            else:
                reason = "no longer defined (YAML or helper removed)"
            _add(entry, "restored", CATEGORY_SAFE, reason, state="restored")
            continue

        # 4. Unavailable for a long time, but still provided: it will come back
        if (not restored and state_obj and state_obj.state == "unavailable"
                and platform not in ALWAYS_UNAVAILABLE_PLATFORMS
                and entry.disabled_by is None):
            age_h = (now - state_obj.last_changed).total_seconds() / 3600
            if age_h >= min_age_hours:
                _add(entry, "unavailable", CATEGORY_UNAVAILABLE,
                     "unavailable, but still provided: deleting it only lasts until the next reload",
                     age_h=age_h, state="unavailable")
            continue

        # 5. Heuristic (opt-in): registry entries without a config entry
        if aggressive and not cfg_entry_id and platform and platform not in MANUAL_PLATFORMS:
            _add(entry, "heuristic", CATEGORY_REVIEW,
                 "no config entry (YAML platform?): check before deleting")

    _LOGGER.info(
        "Scan: %d total, %d candidates (safe:%d review:%d unavailable:%d)%s",
        len(entity_registry.entities), len(orphans),
        sum(1 for o in orphans if o.category == CATEGORY_SAFE),
        sum(1 for o in orphans if o.category == CATEGORY_REVIEW),
        sum(1 for o in orphans if o.category == CATEGORY_UNAVAILABLE),
        " - start-up grace active, restored entities not checked yet" if grace else "",
    )
    return orphans


def detect_orphan_devices(hass: HomeAssistant) -> list[dict]:
    """Devices with no entities left and no existing config entry."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    used = {e.device_id for e in entity_registry.entities.values() if e.device_id}
    found = []
    for device in device_registry.devices.values():
        if device.id in used:
            continue
        if any(hass.config_entries.async_get_entry(eid) for eid in device.config_entries):
            continue
        found.append({
            "device_id": device.id,
            "name": device.name_by_user or device.name or device.id,
            "manufacturer": device.manufacturer,
            "model": device.model,
        })
    return found


async def async_delete_entities(
    hass: HomeAssistant,
    entity_ids: list[str],
) -> tuple[list[str], list[str]]:
    registry = er.async_get(hass)
    deleted: list[str] = []
    failed:  list[str] = []
    for eid in entity_ids:
        entry = registry.async_get(eid)
        if entry is None:
            failed.append(eid)
            continue
        try:
            registry.async_remove(eid)
            deleted.append(eid)
        except Exception as exc:
            _LOGGER.error("Error deleting %s: %s", eid, exc)
            failed.append(eid)
    return deleted, failed


async def async_delete_devices(
    hass: HomeAssistant,
    device_ids: list[str],
) -> tuple[list[str], list[str]]:
    """Remove orphan devices (re-checked: only empty devices with no config entry)."""
    registry = dr.async_get(hass)
    allowed  = {d["device_id"] for d in detect_orphan_devices(hass)}
    deleted: list[str] = []
    failed:  list[str] = []
    for did in device_ids:
        if did not in allowed or registry.async_get(did) is None:
            failed.append(did)
            continue
        try:
            registry.async_remove_device(did)
            deleted.append(did)
        except Exception as exc:
            _LOGGER.error("Error deleting device %s: %s", did, exc)
            failed.append(did)
    return deleted, failed
