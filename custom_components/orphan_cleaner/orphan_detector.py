"""
Orphan entity detection logic.
Operates directly on the HA entity registry and states.

Detection methods:
  1. orphaned_timestamp  — official HA field (non-null)
  2. dead_config_entry   — config_entry_id points to a removed config entry
  3. unloaded_platform   — platform integration is no longer loaded in HA
  4. unavailable_state   — unavailable for more than N hours
  5. heuristic           — no config_entry_id and non-manual platform
"""
from __future__ import annotations

import time
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from .const import MANUAL_PLATFORMS

_LOGGER = logging.getLogger(__name__)

ALWAYS_UNAVAILABLE_PLATFORMS = {
    "template", "group", "universal", "input_boolean",
}

CORE_PLATFORMS = {
    "homeassistant", "persistent_notification", "recorder",
    "frontend", "history", "logbook", "system_log", "mobile_app",
} | MANUAL_PLATFORMS


@dataclass
class OrphanInfo:
    entity_id:   str
    platform:    str
    method:      str
    age_hours:   float | None
    disabled_by: str | None
    state:       str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def detect_orphans(
    hass: HomeAssistant,
    min_age_hours: int = 24,
    aggressive: bool = False,
) -> list[OrphanInfo]:

    entity_registry   = er.async_get(hass)
    now               = time.time()
    orphans: list[OrphanInfo] = []

    active_entry_ids: set[str] = {
        e.entry_id for e in hass.config_entries.async_entries()
    }

    # Loaded integrations = domains of active config entries + HA built-ins
    loaded_integrations: set[str] = {
        e.domain for e in hass.config_entries.async_entries()
    } | CORE_PLATFORMS

    _LOGGER.debug(
        "Scan: %d entities, %d active entries, %d loaded integrations",
        len(entity_registry.entities), len(active_entry_ids), len(loaded_integrations),
    )

    seen: set[str] = set()

    for entry in entity_registry.entities.values():
        platform     = entry.platform or ""
        cfg_entry_id = entry.config_entry_id

        # ── Method 1: orphaned_timestamp ──────────────────────────────
        ts = getattr(entry, "orphaned_timestamp", None)
        if ts is not None:
            age_h = (now - ts) / 3600
            if age_h >= min_age_hours:
                orphans.append(OrphanInfo(
                    entity_id   = entry.entity_id,
                    platform    = platform or "—",
                    method      = "timestamp",
                    age_hours   = round(age_h, 1),
                    disabled_by = entry.disabled_by,
                    state       = "orphaned",
                ))
                seen.add(entry.entity_id)
            continue

        # ── Method 2: dead or failed/not-loaded config entry ────────
        if cfg_entry_id:
            cfg_entry_obj = hass.config_entries.async_get_entry(cfg_entry_id)
            is_dead = cfg_entry_obj is None
            if not is_dead and cfg_entry_obj is not None:
                from homeassistant.config_entries import ConfigEntryState
                bad_states = {
                    ConfigEntryState.NOT_LOADED,
                    ConfigEntryState.SETUP_ERROR,
                    ConfigEntryState.SETUP_RETRY,
                    ConfigEntryState.FAILED_UNLOAD,
                    ConfigEntryState.MIGRATION_ERROR,
                }
                is_dead = cfg_entry_obj.state in bad_states
            if is_dead:
                orphans.append(OrphanInfo(
                    entity_id   = entry.entity_id,
                    platform    = platform or "—",
                    method      = "dead_entry",
                    age_hours   = None,
                    disabled_by = entry.disabled_by,
                ))
                seen.add(entry.entity_id)
                continue

        # ── Method 3: platform no longer loaded ───────────────────────
        if (
            platform
            and platform not in CORE_PLATFORMS
            and platform not in loaded_integrations
        ):
            cfg_entry = hass.config_entries.async_get_entry(cfg_entry_id) if cfg_entry_id else None
            if cfg_entry is None or cfg_entry.domain not in loaded_integrations:
                orphans.append(OrphanInfo(
                    entity_id   = entry.entity_id,
                    platform    = platform or "—",
                    method      = "unloaded_platform",
                    age_hours   = None,
                    disabled_by = entry.disabled_by,
                ))
                seen.add(entry.entity_id)
                continue

        # ── Method 4: unavailable state ───────────────────────────────
        if platform not in ALWAYS_UNAVAILABLE_PLATFORMS and entry.disabled_by is None:
            state_obj = hass.states.get(entry.entity_id)
            if state_obj and state_obj.state == "unavailable":
                modified_at = getattr(entry, "modified_at", None)
                if modified_at:
                    age_h = (datetime.now(timezone.utc) - modified_at).total_seconds() / 3600
                else:
                    created_at = getattr(entry, "created_at", None)
                    age_h = (
                        (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
                        if created_at else 0
                    )
                if age_h >= min_age_hours:
                    orphans.append(OrphanInfo(
                        entity_id   = entry.entity_id,
                        platform    = platform or "—",
                        method      = "unavailable",
                        age_hours   = round(age_h, 1),
                        disabled_by = entry.disabled_by,
                        state       = "unavailable",
                    ))
                    seen.add(entry.entity_id)
                    continue

        # ── Method 5: heuristic ───────────────────────────────────────
        if aggressive and not cfg_entry_id and platform and platform not in MANUAL_PLATFORMS:
            if entry.entity_id not in seen:
                orphans.append(OrphanInfo(
                    entity_id   = entry.entity_id,
                    platform    = platform,
                    method      = "heuristic",
                    age_hours   = None,
                    disabled_by = entry.disabled_by,
                ))

    _LOGGER.info(
        "Scan complete: %d total, %d orphans "
        "(timestamp:%d dead_entry:%d unloaded:%d unavailable:%d heuristic:%d)",
        len(entity_registry.entities), len(orphans),
        sum(1 for o in orphans if o.method == "timestamp"),
        sum(1 for o in orphans if o.method == "dead_entry"),
        sum(1 for o in orphans if o.method == "unloaded_platform"),
        sum(1 for o in orphans if o.method == "unavailable"),
        sum(1 for o in orphans if o.method == "heuristic"),
    )
    return orphans


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
            _LOGGER.warning("Entity not found in registry: %s", eid)
            failed.append(eid)
            continue
        try:
            registry.async_remove(eid)
            _LOGGER.info("Deleted: %s", eid)
            deleted.append(eid)
        except Exception as exc:
            _LOGGER.error("Error deleting %s: %s", eid, exc)
            failed.append(eid)

    return deleted, failed
