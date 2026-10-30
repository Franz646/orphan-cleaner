# Orphan Entity Cleaner - Home Assistant Integration

[![HACS Default](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue)](https://www.home-assistant.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://github.com/Franz646/orphan-cleaner/blob/main/LICENSE)
[![GitHub Release](https://img.shields.io/github/v/release/Franz646/orphan-cleaner)](https://github.com/Franz646/orphan-cleaner/releases)
[![Last Commit](https://img.shields.io/github/last-commit/Franz646/orphan-cleaner)](https://github.com/Franz646/orphan-cleaner/commits/main)
[![Maintainer](https://img.shields.io/badge/maintainer-Francesco%20Beghi-blue)](https://github.com/Franz646)
[![Maintained](https://img.shields.io/badge/maintained-yes-green)](https://github.com/Franz646/orphan-cleaner)
[![Buy Me a Coffee](https://img.buymeacoffee.com/button-api/?text=Buy%20me%20a%20coffee&emoji=&slug=DJvC5DnVJf&button_colour=FFDD00&font_colour=000000&font_family=Cookie&outline_colour=000000&coffee_colour=ffffff)](https://www.buymeacoffee.com/DJvC5DnVJf)

A custom integration that finds and deletes **orphan entities** - entities left in the registry after the integration that created them has been removed or failed - via a web panel in the sidebar and services callable from scripts and automations.

---

## Installation

### Via HACS (recommended)

[![Open HACS Repository](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Franz646&repository=orphan-cleaner&category=integration)
[![Add Integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=orphan_cleaner)

1. Open HACS in your Home Assistant instance
2. Search for **Orphan Entity Cleaner** and install
3. Restart Home Assistant
4. **Settings → Devices & Services → Add Integration → Orphan Entity Cleaner**

### Manual installation

1. Copy the `custom_components/orphan_cleaner/` folder to `<config>/custom_components/`
2. Restart Home Assistant
3. **Settings → Devices & Services → Add Integration → Orphan Entity Cleaner**

---

## Web Panel

After installation, the **Orphan Cleaner** icon appears in the HA sidebar. All settings are controlled directly from the panel - no configuration flow needed after the initial setup.

### Controls

| Control | Description |
|---|---|
| **Scan** | Scans the registry and populates the table |
| **Heuristic** | Enables the heuristic detection (see below) |
| **Min age (h)** | How long an entity must have been unavailable before it is listed (only unavailable entities) |
| **Ignore** | Add platforms or globs to exclude from the current session |
| **Default ignore list** | Persistent ignore list, pre-loaded on every scan (see below) |
| **Dry run** | Simulate deletion without removing anything (see below) |
| **Filter** | Filter visible results by entity_id or platform |
| **Select safe / Deselect** | Selects only the entities that are safe to delete and not used anywhere |
| **Column headers** | Click to sort by Entity ID, Platform, Category or Age - click again to reverse |
| **Platform badge** | Click on any platform badge to instantly select all entities of that platform |
| **Category filter** | Dropdown to show only safe, to review or only unavailable entities |
| **Delete selected** | Delete selected entities with a confirmation dialog |
| **Save & Delete** | Save a JSON backup of selected entities to `/config/orphan_cleaner_backups/` before deleting |
| **Remove orphan devices** | Shown when devices with no entities and no integration are found |

### Ignore (session)

Type a platform name or glob pattern in the **Ignore** field in the control bar and press **Enter** or **+ Add**. Ignored entities remain visible in the table but are greyed out and non-interactive. The orphan counter reflects the exclusion. This list is temporary and resets on page reload.

### Default ignore list (persistent)

A collapsible section below the control bar. Entries here are saved to the integration's config entry options and automatically loaded on every scan and page load. Supports:

- **Platform names** - `tuya`, `shelly`, `imou_life`
- **Platform globs** - `imou_*`, `tuya_*`
- **Entity ID globs** - `sensor.old_*`, `*_deprecated`, `sensor.*_temp`

Entries are saved automatically when added or removed - no Save button needed. Use the **?** link for a full syntax reference.

### Save & Delete

**Save & Delete** exports a timestamped JSON backup of the selected entities to `/config/orphan_cleaner_backups/orphan_cleaner_backup_<timestamp>.json` before proceeding with deletion. If the backup fails, deletion is aborted. The backup contains entity metadata (entity_id, platform, detection method, age, disabled state) and can be used as a reference in case of accidental deletion.

### Dry run

Enable the **Dry run** checkbox in the toolbar before deleting. When active:

- An amber warning banner appears to remind you that no changes will be made
- **Delete selected** becomes **Simulate**
- **Save & Delete** is hidden
- Clicking **Simulate** highlights the selected entities with a `would delete` badge for 6 seconds and logs the result - nothing is actually removed

Dry run is also available as a parameter in the `orphan_cleaner.delete_orphans` service (see Services section).

### Scan comparison

After the first scan, every subsequent scan shows a diff banner above the table:

> *vs previous scan: 3 new ⬆ · 1 gone ⬇ · 108 unchanged*

Entities that are new since the last scan are highlighted with a yellow `new` badge. The banner is hidden when results are identical to the previous scan.

### Sortable columns

Click any column header in the results table to sort by that field. Click again to reverse the order. The active sort direction is indicated by ↑ or ↓ next to the column name. Sortable columns: **Entity ID**, **Platform**, **Category**, **Age**.

### Category breakdown

After each scan, a compact bar appears below the stat cards:

> *59 safe · 36 to review · 4 only unavailable · 2 still used*

### Category filter

A dropdown in the toolbar lets you show only one category: **Safe to delete**, **To review** or **Only unavailable**. Combine it with the text filter for precise results.

### Still used

Entities still referenced by automations, scripts or scenes get a red **used by N** badge (hover it to see where). They are never selected by **Select safe**, and the confirmation dialog warns you if you selected them manually.

### Platform badge click

Click any platform badge in the results table to instantly select all entities of that platform. Useful for quickly selecting a full group before deleting or ignoring.

---

## Detection and categories

Every candidate gets a **category**, which tells how safe it is to delete it, and a short **reason**.

| Category | Meaning | Included in "delete all"? |
|---|---|---|
| **Safe** | Nothing provides the entity any more: its integration was removed, or Home Assistant restored it from the registry (state attribute `restored: true`, the yellow "no longer provided" warning) while its integration is running. | Yes |
| **To review** | Its integration is disabled, failing or retrying setup, or it was found by the heuristic. It may come back on its own. | No |
| **Only unavailable** | Its integration still provides it, but it has been `unavailable` for at least **Min age (h)** (device off or unreachable). Deleting it only lasts until the next reload. | No |

Detection steps, in order:

1. **Removed integration** - the entity's config entry no longer exists → *safe*.
2. **Integration not running** - the config entry is disabled, not loaded, in setup error, retrying setup or in migration error → *to review*.
3. **No longer provided** - the state has `restored: true` → *safe*. Skipped during the first 10 minutes after Home Assistant starts, while integrations are still loading (the panel shows a notice).
4. **Unavailable** - unavailable for at least **Min age (h)**, measured from the state's last change (not from when the entity was created) → *only unavailable*.
5. **Heuristic** (optional, **Heuristic** checkbox) - no config entry and a platform not in the exclusion list → *to review*.

Heuristic exclusion list: `automation`, `counter`, `group`, `input_boolean`, `input_button`, `input_datetime`, `input_number`, `input_select`, `input_text`, `person`, `persistent_notification`, `scene`, `schedule`, `script`, `tag`, `template`, `timer`, `zone`

### Orphan devices

Devices that have no entities left and whose integration no longer exists are listed separately and can be removed with one click, or with the `orphan_cleaner.delete_orphan_devices` service.

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
count_safe: 3
startup_grace: false
orphans:
  - entity_id: sensor.old_shelly
    platform: shelly
    method: restored
    category: safe
    reason: no longer provided by its integration
    age_hours: null
    disabled_by: null
    used_in: []
orphan_devices:
  - device_id: 0123abcd...
    name: Old plug
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
      message: "Found {{ trigger.event.data.count_safe }} orphan entities safe to delete."
```

### `orphan_cleaner.delete_orphans`

Deletes the specified entities or, if none are specified, only the candidates in the **safe** category.

| Field | Type | Required | Description |
|---|---|---|---|
| `entity_ids` | list | No | Entities to delete. If omitted → only the *safe* orphans |
| `dry_run` | bool | No | Log only, without making changes (default: `false`) |

```yaml
# Delete all safe orphans
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

### `orphan_cleaner.delete_orphan_devices`

Removes devices with no entities left whose integration no longer exists. Without `device_ids`, removes all of them. Supports `dry_run`.

```yaml
action: orphan_cleaner.delete_orphan_devices
data:
  dry_run: true
```

Set `force: true` to remove specific devices from the device registry even when they are not detected as orphans (for example a stale device whose integration is still installed). `force` requires `device_ids`, and the device's entities are removed with it.

```yaml
action: orphan_cleaner.delete_orphan_devices
data:
  device_ids:
    - 0123456789abcdef0123456789abcdef
  force: true
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

If you used **Save & Delete**, a backup file was written to `/config/orphan_cleaner_backups/orphan_cleaner_backup_<timestamp>.json` before the deletion. This file contains the metadata of all deleted entities.

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

- **Check if the entity was truly orphaned** - look at the `method` and `age_hours` fields. If `age_hours` is low, the integration may have been temporarily offline and the entity could reappear after a restart.
- **Reinstall the integration** - if the platform (e.g. `tuya`, `shelly`, `zha`) is still active and the physical device is reachable, removing and re-adding the integration will recreate its entities automatically.
- **Restore custom attributes manually** - if the entity reappears, you can reassign its area, icon, and aliases from the HA UI. The backup gives you the original `entity_id` to match it.
- **Clean up the recorder** - if the entity had historical data and you want to remove it, use the `recorder.purge_entities` service with the `entity_id` from the backup.

### What cannot be recovered

- The entity registry entry itself - HA does not expose an API to re-insert entries manually.
- Historical recorder data is not deleted by this integration, but it will no longer be linked to an active entity.
- If the underlying integration or device no longer exists, the entity cannot be recreated without it.

---

## Security

All API endpoints require Home Assistant authentication. The panel itself requires admin privileges to access from the sidebar (`require_admin`). Endpoints that delete entities or write files to the configuration directory (`/delete`, `/export`) additionally require an admin-level account, regardless of how they are called. Read-only endpoints (`/scan`, `/ignore_list` GET) require a valid authenticated session but not admin rights.

---

## Warnings

- **Always make a backup** before deleting entities in bulk. Use **Save & Delete** to automatically export a JSON record before each deletion.
- Deleted entities are removed from the **registry**: historical data in the **recorder** remains but is no longer associated with an active entity. To clean the recorder as well, use the `recorder.purge_entities` service.
- Entities in the **to review** and **only unavailable** categories may come back after a reload or when their integration recovers: deleting them only loses their customisations (name, area, icon).
- Deletion is **irreversible**. Entities cannot be restored from the backup - the backup is a reference record only.

---

## License

MIT
