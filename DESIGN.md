# AE2 Bus Scanner Design

## Goal

Build a small Windows `.exe` tool that helps players scan a Minecraft save for AE2 buses and interfaces that contain selected filter items.

The user flow should be:

1. Choose a Minecraft save folder.
2. The tool discovers available dimensions.
3. User selects one or more dimensions.
4. User enters or selects one or more item IDs, for example `gtceu:hydrogen` or `minecraft:water`.
5. User clicks Scan.
6. The tool scans the selected dimensions and shows matching AE2 parts:
   - AE2 import bus
   - AE2 export bus
   - AE2 ME interface / cable interface
7. User can export the result as JSON or CSV.

The prototype work has already confirmed the important storage detail:

- Many AE2 parts are not standalone blocks.
- They are stored inside a block entity with `id = ae2:cable_bus`.
- The part data lives in side keys: `up`, `down`, `north`, `south`, `west`, `east`.
- Each side part has its own `id`, for example `ae2:export_bus`, `ae2:import_bus`, `ae2:cable_interface`.
- Filter items are usually stored in the part's `config` list.

## Recommended Stack

Use Python for the first `.exe` version.

Suggested libraries:

- `anvil-parser2`: reads `.mca` region files and chunk NBT.
- `nbt`: dependency used by `anvil-parser2`.
- `PySide6`: desktop GUI.
- `PyInstaller`: package the app into a Windows `.exe`.

Why Python first:

- We already have a working scanner prototype.
- NBT logic is finicky, and the current Python path is proven against this save.
- PyInstaller can produce a practical standalone tool quickly.
- Performance is already acceptable when using the cable-bus fast path and multiprocessing.

Potential later rewrite:

- A Rust or C# scanner could be faster and more polished, but only after the NBT rules are fully known.
- The first version should prioritize correctness and useful output.

## Project Layout

Proposed structure:

```text
ae2_bus_scanner/
  DESIGN.md
  README.md
  requirements.txt
  pyproject.toml
  src/
    ae2_bus_scanner/
      __init__.py
      app.py
      cli.py
      gui/
        main_window.py
        widgets.py
      scanner/
        __init__.py
        dimensions.py
        engine.py
        models.py
        nbt_utils.py
        exporters.py
      resources/
        app.ico
  tests/
    test_filter_matching.py
    test_dimension_discovery.py
  scripts/
    build_exe.ps1
```

The current prototype script can be split into:

- `scanner/nbt_utils.py`: tag helpers like `tag_value()` and `tag_to_python()`.
- `scanner/dimensions.py`: discover dimensions and region folders.
- `scanner/engine.py`: scan region files, chunks, AE2 parts, and filter configs.
- `scanner/models.py`: typed result objects.
- `scanner/exporters.py`: JSON and CSV export.
- `gui/main_window.py`: save picker, dimension checklist, item selector, scan progress, results table.

## Dimension Discovery

The tool should accept a save directory, not a single `region` folder.

Example save path:

```text
D:\Minecraft\PCL2\.minecraft\versions\Create New Horizon\saves\[CTNH]server-backup
```

Dimension discovery rules:

- Overworld:
  - `<save>/region`
  - display name: `minecraft:overworld`
- Nether:
  - `<save>/DIM-1/region`
  - display name: `minecraft:the_nether`
- End:
  - `<save>/DIM1/region`
  - display name: `minecraft:the_end`
- Modded dimensions:
  - `<save>/dimensions/<namespace>/<path>/region`
  - display name: `<namespace>:<path>`

Examples from this save:

- `javd:void`
- `ad_astra:moon`
- `ad_astra:mars`
- `aether:the_aether`
- `twilightforest:twilight_forest`

Dimension metadata should include:

```python
DimensionInfo(
    id="javd:void",
    display_name="javd:void",
    region_dir=Path(".../dimensions/javd/void/region"),
    region_count=55,
    total_bytes=...,
    last_modified=...
)
```

The GUI should show dimensions in a checklist with region count and size, so the user can avoid huge scans accidentally.

## AE2 Data Model

### Standalone Block Entities

Some AE2 blocks are standalone tile entities:

- `ae2:interface`
- possibly controller, quantum ring, pattern provider, etc.

For this tool, standalone scanning should include at least:

- `ae2:interface`

The current tested `ae2:interface` examples did not expose filters in the same `config` shape, but the scanner should keep a generic recursive item extractor for standalone blocks.

### Cable Bus Parts

The important case is:

```nbt
{
  id: "ae2:cable_bus",
  x: 448,
  y: 129,
  z: 14,
  east: {
    id: "ae2:export_bus",
    config: [
      { "#": 0, "#c": "ae2:f", id: "biofactory:nutrients_fluid" },
      { "#": 0, "#c": "ae2:i", id: "biomancy:living_flesh" }
    ],
    fuzzy_mode: "IGNORE_ALL",
    craft_only: "NO",
    redstone_controlled: "IGNORE"
  }
}
```

Side keys:

```python
SIDE_KEYS = ("up", "down", "north", "south", "west", "east")
```

Part IDs to support in v1:

```python
TARGET_PART_IDS = {
    "ae2:import_bus",
    "ae2:export_bus",
    "ae2:cable_interface",
}
```

Possible additional IDs for later:

- `ae2:storage_bus`
- `ae2:pattern_provider`
- `ae2:cable_pattern_provider`
- Add-on parts such as `expatternprovider:*`

## Filter Matching

The scanner should normalize every filter slot into:

```python
FilterItem(
    id="gtceu:hydrogen",
    kind="fluid" | "item" | "unknown",
    count=None,
    slot=0,
    raw={...}
)
```

AE2 appears to use:

- `#c = ae2:i` for item filters.
- `#c = ae2:f` for fluid filters.
- Empty slots may be `{}` and should be ignored.

User matching should support:

- Exact item ID:
  - `gtceu:hydrogen`
  - `minecraft:water`
- Multiple IDs:
  - newline input or comma-separated input.
- Optional partial/fuzzy search in the UI for convenience:
  - Search text `hydrogen` can suggest `gtceu:hydrogen` from discovered filters.

Recommended matching modes:

- `Exact ID`: default and safest.
- `Contains`: useful when the user only remembers part of a name.
- `All`: show all buses/interfaces, ignoring item filter.

The scan engine should return both:

- all matched devices
- all discovered filter item IDs, so the UI can populate suggestions after the first scan.

## Result Model

Use a stable JSON-friendly result shape:

```json
{
  "dimension": "javd:void",
  "region": "r.0.0.mca",
  "chunk": [28, 0],
  "pos": [448, 129, 14],
  "block": "ae2:cable_bus",
  "part_side": "east",
  "part_id": "ae2:export_bus",
  "filters": [
    {
      "id": "biofactory:nutrients_fluid",
      "kind": "fluid",
      "slot": 0
    },
    {
      "id": "biomancy:living_flesh",
      "kind": "item",
      "slot": 10
    }
  ],
  "settings": {
    "fuzzy_mode": "IGNORE_ALL",
    "craft_only": "NO",
    "redstone_controlled": "IGNORE",
    "scheduling_mode": "DEFAULT"
  }
}
```

CSV columns:

```text
dimension,region,chunk_x,chunk_z,x,y,z,part_id,side,filter_ids,filter_kinds
```

## Scanning Engine

### Fast Cable Bus Path

This is the default scan path for v1.

Algorithm:

1. For each selected dimension, list non-empty `r.*.*.mca` files.
2. For each region file:
   1. Open with `anvil.Region.from_file()`.
   2. Iterate local chunk coordinates `0..31`, `0..31`.
   3. Skip missing chunks via `region.chunk_location(cx, cz) == (0, 0)`.
   4. Load chunk with `region.get_chunk(cx, cz)`.
   5. Iterate `chunk.tile_entities`.
   6. Keep only tile entities where `id == ae2:cable_bus`.
   7. Check all side keys.
   8. If side part ID is in target part IDs, normalize `config`.
   9. Apply item filter matching.
   10. Emit results.

Important performance rule:

- Do not call `chunk.get_block()` in the fast path.
- Do not convert the whole tile entity to a Python dict unless the part already matched.
- Use small tag helpers to read `id`, `x`, `y`, `z`, `config`.

This is what made the `javd:void` scan finish in about 3 seconds for the tested save.

### Standalone Interface Path

Standalone `ae2:interface` requires checking block entity IDs directly.

Algorithm:

1. In addition to `ae2:cable_bus`, check tile entity `id`.
2. If `id in STANDALONE_TARGET_IDS`, extract filters with a generic recursive item extractor.
3. Apply user item matching.

This may be slower than the cable path if implemented naively, but standalone tile entities are much fewer than all blocks. It should still avoid `chunk.get_block()`.

### Multiprocessing

Parallelize by region file.

Use:

```python
ProcessPoolExecutor(max_workers=workers)
```

Worker input:

```python
ScanTask(
    dimension_id="javd:void",
    region_file=Path(".../r.0.0.mca"),
    target_part_ids={...},
    target_item_ids={...},
    match_mode="exact"
)
```

Worker output:

```python
ScanResultBatch(
    matches=[...],
    stats={...},
    errors=[...]
)
```

Default worker count:

```python
min(os.cpu_count() or 1, 8)
```

The GUI should expose this as an advanced option, defaulting to `Auto`.

## GUI Design

Use a practical desktop layout.

Main window sections:

- Save selector:
  - Text field showing selected save path.
  - Browse button.
  - Recent saves dropdown.
- Dimension selector:
  - Checklist table.
  - Columns: selected, dimension, region count, size, last modified.
  - Quick buttons: Select All, Select None, Select Recent, Select Void-like.
- Target selector:
  - Checkboxes for device types:
    - Import Bus
    - Export Bus
    - ME Interface
  - Item ID input:
    - Multi-line text box.
    - One item ID per line.
    - Optional paste support for comma-separated IDs.
  - Match mode:
    - Exact
    - Contains
    - Show All
- Scan controls:
  - Scan button.
  - Cancel button.
  - Progress bar.
  - Status label: current dimension, region progress, matches found.
- Results table:
  - Dimension
  - Position
  - Device
  - Side
  - Filter items
  - Region
  - Chunk
- Export buttons:
  - Export JSON
  - Export CSV

The first version can be simple but should feel focused: this is a diagnostic tool, not a launcher.

## Cancellation and Progress

The GUI must not freeze during scanning.

Recommended approach:

- Run scan from a background `QThread`.
- The thread owns a scan coordinator.
- The coordinator uses `ProcessPoolExecutor` for region workers.
- The GUI receives progress signals:
  - dimensions discovered
  - scan started
  - region completed
  - result batch received
  - scan finished
  - error received

Cancellation:

- Keep a shared cancel flag in the coordinator.
- Stop submitting new tasks once cancellation is requested.
- For already-running process workers, allow them to finish their current region.
- Show partial results.

## File Outputs

JSON export should be UTF-8.

Avoid PowerShell redirection for app-generated files. Use:

```python
Path(out_path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
```

CSV export should use UTF-8 with BOM only if Excel compatibility is important.

Recommended:

- JSON: UTF-8 without BOM.
- CSV: UTF-8 with BOM, because Windows Excel handles it better.

## Packaging as EXE

Use PyInstaller first.

Requirements:

```text
anvil-parser2
nbt
frozendict
PySide6
pyinstaller
```

Build command:

```powershell
python -m PyInstaller `
  --name AE2BusScanner `
  --windowed `
  --onefile `
  --icon src/ae2_bus_scanner/resources/app.ico `
  src/ae2_bus_scanner/app.py
```

Potential packaging issues:

- `PySide6` makes the `.exe` larger.
- Multiprocessing in a frozen exe needs:

```python
if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
```

- PyInstaller may need hidden imports for `anvil` or `nbt` if auto-detection misses them.

Fallback build command:

```powershell
python -m PyInstaller `
  --name AE2BusScanner `
  --windowed `
  --onefile `
  --hidden-import anvil `
  --hidden-import nbt `
  src/ae2_bus_scanner/app.py
```

## Validation Plan

Use the known `javd:void` dimension as a fixture during development.

Known expected scan from the current save:

- Dimension: `javd:void`
- Target path: `saves/[CTNH]server-backup/dimensions/javd/void/region`
- Cable bus part matches:
  - total: `399`
  - `ae2:export_bus`: `141`
  - `ae2:cable_interface`: `258`
  - entries with filters: at least `153`

The first automated smoke test can assert these counts against a local fixture only when that fixture exists. The public test suite should use a tiny synthetic or copied region file later.

Manual validation checklist:

- Select save folder.
- Confirm `javd:void` appears in dimension list.
- Select only `javd:void`.
- Select Export Bus and Cable Interface.
- Match mode: Show All.
- Scan finishes in a few seconds on the tested save.
- Result count is close to the known expected count.
- Enter `biofactory:nutrients_fluid`.
- Scan returns many export buses with that fluid filter.
- Export JSON opens as UTF-8.
- Export CSV opens in Excel.

## Implementation Milestones

### Milestone 1: Scanner Library

Deliver:

- Dimension discovery.
- Cable bus part scanner.
- Item filter matching.
- JSON and CSV export.
- CLI command for quick validation.

CLI example:

```powershell
ae2-bus-scanner scan `
  --save "D:\...\saves\[CTNH]server-backup" `
  --dimension javd:void `
  --part ae2:export_bus `
  --item biofactory:nutrients_fluid `
  --out result.json
```

### Milestone 2: GUI Prototype

Deliver:

- Save folder picker.
- Dimension checklist.
- Device type checkboxes.
- Item ID input.
- Scan button.
- Results table.
- Export JSON.

### Milestone 3: Performance and UX

Deliver:

- Multiprocessing worker count option.
- Progress reporting by region.
- Cancel scan.
- Recent save paths.
- CSV export.
- Better result sorting and filtering.

### Milestone 4: EXE Build

Deliver:

- PyInstaller build script.
- App icon.
- Version metadata.
- A zip release containing the `.exe` and README.

## Risks and Open Questions

### AE2 Version Differences

Different AE2 versions may store parts differently. The scanner should keep raw `part_data` in JSON output for unknown cases, and logs should report unknown AE2 side part IDs.

### Import Bus Config Shape

The current prototype focused on export bus and cable interface. Import buses use the same `config` pattern in observed data, so they should be supported by adding `ae2:import_bus` to target part IDs.

### Standalone ME Interface Filters

Standalone `ae2:interface` examples from the tested world did not show obvious filter config. The scanner should include standalone interfaces in results, but filter extraction may need more samples.

### Add-on Interfaces

Mods such as ExtendedAE or Extended Pattern Provider may add interface-like parts with their own IDs. Keep the scanner modular so target part IDs can be configured later.

## Suggested Next Step

Start by turning the current prototype into a scanner package with a CLI. Once the CLI returns the same `javd:void` counts quickly, add the GUI on top. This keeps the NBT and performance logic testable without clicking through the app.
