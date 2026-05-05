# Orphan Entity Cleaner — Custom Integration for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue)](https://www.home-assistant.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://github.com/Franz646/orphan-cleaner/blob/main/LICENSE)
[![GitHub Release](https://img.shields.io/github/v/release/Franz646/orphan-cleaner)](https://github.com/Franz646/orphan-cleaner/releases)
[![Last Commit](https://img.shields.io/github/last-commit/Franz646/orphan-cleaner)](https://github.com/Franz646/orphan-cleaner/commits/main)

A custom integration that finds and deletes **orphan entities** — entities left in the registry after the integration that created them has been removed or failed — via a web panel in the sidebar and services callable from scripts and automations.

---

## Installation

### Via HACS (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Franz646&repository=orphan-cleaner&category=Integration)

1. In HACS → **Integrations → ⋮ → Custom repositories**
2. Add the URL of this repository, category **Integration**
3. Search for **Orphan Entity Cleaner** and install
4. Restart Home Assistant
5. **Settings → Devices & Services → Add Integration → Orphan Entity Cleaner**

### Manual installation

1. Copy the `custom_components/orphan_cleaner/` folder to `<config>/custom_components/`
2. Restart Home Assistant
3. **Settings → Devices & Services → Add Integration → Orphan Entity Cleaner**

---

## Web Panel

After installation, the **Orphan Cleaner** icon appears in the HA sidebar. All settings are controlled directly from the panel — no configuration flow needed after the initial setup.

### Controls

| Control | Description |
|---|---|
| **Scan** | Scans the registry and populates the table |
| **Heuristic** | Enables detection method 4 (see below) |
| **Min age (h)** | Minimum age in hours for an entity to be flagged |
| **Ignore** | Add platforms or globs to exclude from the current session |
| **Default ignore list** | Persistent ignore list, pre-loaded on every scan (see below) |
| **Dry run** | Simulate deletion without removing anything (see below) |
| **Filter** | Filter visible results by entity_id or platform |
| **Select all / Deselect** | Bulk checkbox controls |
| **Column headers** | Click to sort by Entity ID, Platform, Detection or Age — click again to reverse |
| **Delete selected** | Delete selected entities with a confirmation dialog |
| **Save & Delete** | Save a JSON backup of selected entities to `/config/` before deleting |

### Ignore (session)

Type a platform name or glob pattern in the **Ignore** field in the control bar and press **Enter** or **+ Add**. Ignored entities remain visible in the table but are greyed out and non-interactive. The orphan counter reflects the exclusion. This list is temporary and resets on page reload.

### Default ignore list (persistent)

A collapsible section below the control bar. Entries here are saved to the integration's config entry options and automatically loaded on every scan and page load. Supports:

- **Platform names** — `tuya`, `shelly`, `imou_life`
- **Platform globs** — `imou_*`, `tuya_*`
- **Entity ID globs** — `sensor.old_*`, `*_deprecated`, `sensor.*_temp`

Press **💾 Save** to persist the current list. Use the **?** link for a full syntax reference.

### Save & Delete

**Save & Delete** exports a timestamped JSON backup of the selected entities to `/config/orphan_cleaner_backup_<timestamp>.json` before proceeding with deletion. If the backup fails, deletion is aborted. The backup contains entity metadata (entity_id, platform, detection method, age, disabled state) and can be used as a reference in case of accidental deletion.

### Dry run

Enable the **Dry run** checkbox in the toolbar before deleting. When active:

- An amber warning banner appears to remind you that no changes will be made
- **Delete selected** becomes **Simulate**
- **Save & Delete** is hidden
- Clicking **Simulate** highlights the selected entities with a `would delete` badge for 6 seconds and logs the result — nothing is actually removed

Dry run is also available as a parameter in the `orphan_cleaner.delete_orphans` service (see Services section).

### Scan comparison

After the first scan, every subsequent scan shows a diff banner above the table:

> *vs previous scan: 3 new ⬆ · 1 gone ⬇ · 108 unchanged*

Entities that are new since the last scan are highlighted with a yellow `new` badge. The banner is hidden when results are identical to the previous scan.

### Sortable columns

Click any column header in the results table to sort by that field. Click again to reverse the order. The active sort direction is indicated by ↑ or ↓ next to the column name. Sortable columns: **Entity ID**, **Platform**, **Detection**, **Age**.

---

## Detection Methods

### Method 1 — `orphaned_timestamp` (reliable)

Home Assistant sets this field in the registry when, after a full restart, an entity is not claimed by any integration. This is the official signal and is always active.

**Min age (h)** filters out recently orphaned entities, useful if an integration is temporarily offline. Ages above 24 hours are displayed in days (e.g. `377d`) in the panel table.

### Method 2 — Dead config entry

If an entity's `config_entry_id` points to a config entry that no longer exists or is in a `FAILED` / `NOT_LOADED` state, the entity is considered an orphan.

### Method 3 — Unavailable state

Entities in `unavailable` state for longer than **Min age (h)** are flagged. Catches entities that HA marks with the yellow warning "no longer provided by the integration".

### Method 4 — Heuristic (optional)

Enabled by the **Heuristic** checkbox. Also flags entities with no `config_entry_id` and a platform not in the following exclusion list:

`automation`, `counter`, `group`, `input_boolean`, `input_button`, `input_datetime`, `input_number`, `input_select`, `input_text`, `person`, `persistent_notification`, `scene`, `schedule`, `script`, `tag`, `template`, `timer`, `zone`

---

## Services

### `orphan_cleaner.scan`

Runs the scan and fires the `orphan_cleaner_orphans_found` event on the HA event bus.

```yaml
action: orphan_cleaner.scan
```

Event payload:
```yaml
count: 5
orphans:
  - entity_id: sensor.old_shelly
    platform: shelly
    method: timestamp
    age_hours: 72.3
    disabled_by: null
```

Example automation:
```yaml
automation:
  trigger:
    platform: event
    event_type: orphan_cleaner_orphans_found
  condition:
    condition: template
    value_template: "{{ trigger.event.data.count > 0 }}"
  action:
    service: notify.mobile_app
    data:
      title: "Orphan entities detected"
      message: "Found {{ trigger.event.data.count }} orphan entities."
```

### `orphan_cleaner.delete_orphans`

Deletes the specified entities, or all detected orphans if none are specified.

| Field | Type | Required | Description |
|---|---|---|---|
| `entity_ids` | list | No | Entities to delete. If omitted → all orphans |
| `dry_run` | bool | No | Log only, without making changes (default: `false`) |

```yaml
# Delete all orphans
action: orphan_cleaner.delete_orphans

# Dry run
action: orphan_cleaner.delete_orphans
data:
  dry_run: true

# Delete specific entities
action: orphan_cleaner.delete_orphans
data:
  entity_ids:
    - sensor.old_device
    - binary_sensor.ghost_sensor
```

---

## File Structure

```
custom_components/orphan_cleaner/
├── __init__.py           ← setup, panel registration, teardown
├── config_flow.py        ← initial config flow
├── const.py              ← constants
├── manifest.json         ← integration metadata
├── orphan_detector.py    ← detection and deletion logic
├── panel_api.py          ← HTTP views (panel, scan, delete, export, ignore list)
├── services.py           ← HA services (scan, delete_orphans)
├── services.yaml         ← service documentation for Developer Tools
├── strings.json          ← UI labels
├── translations/
│   └── en.json
└── frontend/
    ├── panel.html        ← full web interface
    └── orphan-cleaner-panel.js
```

---

## Recovering from accidental deletion

If you used **Save & Delete**, a backup file was written to `/config/orphan_cleaner_backup_<timestamp>.json` before the deletion. This file contains the metadata of all deleted entities.

### What the backup contains

```json
{
  "exported_at": "2024-11-15T10:32:00",
  "entity_count": 3,
  "entities": [
    {
      "entity_id": "sensor.old_device_temperature",
      "platform": "tuya",
      "method": "dead_entry",
      "age_hours": 312.5,
      "disabled_by": null
    }
  ]
}
```

### What you can do

- **Check if the entity was truly orphaned** — look at the `method` and `age_hours` fields. If `age_hours` is low, the integration may have been temporarily offline and the entity could reappear after a restart.
- **Reinstall the integration** — if the platform (e.g. `tuya`, `shelly`, `zha`) is still active and the physical device is reachable, removing and re-adding the integration will recreate its entities automatically.
- **Restore custom attributes manually** — if the entity reappears, you can reassign its area, icon, and aliases from the HA UI. The backup gives you the original `entity_id` to match it.
- **Clean up the recorder** — if the entity had historical data and you want to remove it, use the `recorder.purge_entities` service with the `entity_id` from the backup.

### What cannot be recovered

- The entity registry entry itself — HA does not expose an API to re-insert entries manually.
- Historical recorder data is not deleted by this integration, but it will no longer be linked to an active entity.
- If the underlying integration or device no longer exists, the entity cannot be recreated without it.

---

## Warnings

- **Always make a backup** before deleting entities in bulk. Use **Save & Delete** to automatically export a JSON record before each deletion.
- Deleted entities are removed from the **registry**: historical data in the **recorder** remains but is no longer associated with an active entity. To clean the recorder as well, use the `recorder.purge_entities` service.
- An entity with `orphaned_timestamp` may belong to an integration that is temporarily offline. Increase **Min age (h)** if you have unstable integrations.
- Deletion is **irreversible**. Entities cannot be restored from the backup — the backup is a reference record only.

---

## License

MIT
