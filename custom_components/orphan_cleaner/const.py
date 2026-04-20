"""Constants for Orphan Entity Cleaner."""

DOMAIN = "orphan_cleaner"

CONF_MIN_AGE_HOURS    = "min_orphan_age_hours"
CONF_AGGRESSIVE       = "aggressive_heuristic"

DEFAULT_MIN_AGE_HOURS = 24
DEFAULT_AGGRESSIVE    = False

# Platforms that are never considered orphans
MANUAL_PLATFORMS = {
    "template", "input_boolean", "input_number", "input_text",
    "input_select", "input_datetime", "input_button", "counter",
    "timer", "schedule", "group", "persistent_notification",
    "script", "automation", "scene", "zone", "person", "tag",
}

# Service names
SERVICE_SCAN           = "scan"
SERVICE_DELETE_ORPHANS = "delete_orphans"

# Service fields
FIELD_ENTITY_IDS = "entity_ids"
FIELD_DRY_RUN    = "dry_run"

# HA event fired after scan
EVENT_ORPHANS_FOUND = f"{DOMAIN}_orphans_found"

# Panel
PANEL_URL  = "orphan-cleaner"
PANEL_NAME = "Orphan Cleaner"
PANEL_ICON = "mdi:broom"

# Current version (used for cache-busting)
VERSION = "1.2.4"
