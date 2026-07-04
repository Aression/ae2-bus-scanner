import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import anvil
from nbt import nbt

from .dimensions import discover_dimensions
from .models import DimensionInfo, FilterItem, ProgressCallback, ScanMatch, ScanOptions
from .nbt_utils import SIDE_KEYS, generic_recursive_items, normalize_config_items_tag, normalize_settings_tag, tag_to_python, tag_value


STANDALONE_TARGET_IDS = {"ae2:interface"}
DEFAULT_PART_IDS = {"ae2:import_bus", "ae2:export_bus", "ae2:cable_interface"}


def _normalize_item_ids(item_ids: Sequence[str]) -> List[str]:
    return [item.strip().lower() for item in item_ids if item and item.strip()]


def _match_item_ids(filters: Sequence[FilterItem], targets: Sequence[str], match_mode: str) -> bool:
    if match_mode == "all" or not targets:
        return True
    filter_ids = [item.id.lower() for item in filters]
    if match_mode == "exact":
        return any(target in filter_ids for target in targets)
    if match_mode == "contains":
        return any(target in filter_id for target in targets for filter_id in filter_ids)
    raise ValueError(f"Unsupported match mode: {match_mode}")


def _build_filter_items(raw_filters: Iterable[Dict[str, Any]]) -> List[FilterItem]:
    items: List[FilterItem] = []
    for raw in raw_filters:
        items.append(
            FilterItem(
                id=raw["id"],
                kind=raw.get("kind", "unknown"),
                count=raw.get("count"),
                slot=raw.get("slot"),
                tag=raw.get("tag"),
            )
        )
    return items


def _match_from_dict(payload: Dict[str, Any]) -> ScanMatch:
    return ScanMatch(
        dimension=payload["dimension"],
        region=payload["region"],
        chunk=payload["chunk"],
        x=payload["x"],
        y=payload["y"],
        z=payload["z"],
        block=payload["block"],
        part_id=payload["part_id"],
        part_side=payload.get("part_side"),
        filters=_build_filter_items(payload.get("filters", [])),
        settings=payload.get("settings", {}),
        raw_fields=payload.get("raw_fields", []),
        part_data=payload.get("part_data"),
    )


def _scan_chunk_for_matches(
    chunk: Any,
    dimension_id: str,
    region_name: str,
    chunk_x: int,
    chunk_z: int,
    target_part_ids: Sequence[str],
    target_items: Sequence[str],
    match_mode: str,
) -> List[ScanMatch]:
    matches: List[ScanMatch] = []
    target_part_ids_set = set(target_part_ids)

    for tile_entity in chunk.tile_entities:
        tile_entity_id = tag_value(tile_entity, "id")
        x = tag_value(tile_entity, "x")
        y = tag_value(tile_entity, "y")
        z = tag_value(tile_entity, "z")
        if x is None or y is None or z is None:
            continue

        if tile_entity_id == "ae2:cable_bus":
            for side in SIDE_KEYS:
                if side not in tile_entity:
                    continue
                side_data = tile_entity[side]
                if not isinstance(side_data, nbt.TAG_Compound):
                    continue
                part_id = tag_value(side_data, "id")
                if part_id not in target_part_ids_set:
                    continue
                filters = _build_filter_items(normalize_config_items_tag(side_data["config"])) if "config" in side_data else []
                if not _match_item_ids(filters, target_items, match_mode):
                    continue
                matches.append(
                    ScanMatch(
                        dimension=dimension_id,
                        region=region_name,
                        chunk=[chunk_x, chunk_z],
                        x=int(x),
                        y=int(y),
                        z=int(z),
                        block="ae2:cable_bus",
                        part_id=part_id,
                        part_side=side,
                        filters=filters,
                        settings=normalize_settings_tag(side_data),
                        raw_fields=["config"] if "config" in side_data else [],
                        part_data=tag_to_python(side_data),
                    )
                )
            continue

        if tile_entity_id in STANDALONE_TARGET_IDS and tile_entity_id in target_part_ids_set:
            raw_items = generic_recursive_items(tile_entity)
            filters = _build_filter_items(
                {
                    "id": entry["item"]["id"],
                    "kind": "unknown",
                    "count": entry["item"].get("Count"),
                    "tag": entry["item"].get("tag"),
                }
                for entry in raw_items
            )
            if not _match_item_ids(filters, target_items, match_mode):
                continue
            matches.append(
                ScanMatch(
                    dimension=dimension_id,
                    region=region_name,
                    chunk=[chunk_x, chunk_z],
                    x=int(x),
                    y=int(y),
                    z=int(z),
                    block=tile_entity_id,
                    part_id=tile_entity_id,
                    part_side=None,
                    filters=filters,
                    settings={},
                    raw_fields=[],
                    part_data=tag_to_python(tile_entity),
                )
            )

    return matches


def _scan_region_task(task: Tuple[str, str, Sequence[str], Sequence[str], str]) -> Tuple[List[Dict[str, Any]], Dict[str, Any], List[str]]:
    region_file_str, dimension_id, target_part_ids, target_items, match_mode = task
    region_file = Path(region_file_str)
    matches: List[Dict[str, Any]] = []
    errors: List[str] = []
    stats = {"region": region_file.name, "chunks_seen": 0, "matches": 0}
    try:
        region = anvil.Region.from_file(str(region_file))
        for chunk_z in range(32):
            for chunk_x in range(32):
                if region.chunk_location(chunk_x, chunk_z) == (0, 0):
                    continue
                stats["chunks_seen"] += 1
                try:
                    chunk = region.get_chunk(chunk_x, chunk_z)
                except Exception:
                    continue
                chunk_matches = _scan_chunk_for_matches(
                    chunk=chunk,
                    dimension_id=dimension_id,
                    region_name=region_file.name,
                    chunk_x=chunk_x,
                    chunk_z=chunk_z,
                    target_part_ids=target_part_ids,
                    target_items=target_items,
                    match_mode=match_mode,
                )
                if chunk_matches:
                    matches.extend(match.to_dict() for match in chunk_matches)
        stats["matches"] = len(matches)
    except Exception as exc:
        errors.append(f"ERROR {dimension_id} {region_file.name}: {exc}")
    return matches, stats, errors


def scan_dimensions(
    save_dir: Path,
    options: ScanOptions,
    progress: Optional[ProgressCallback] = None,
) -> List[ScanMatch]:
    dimensions = {dim.id: dim for dim in discover_dimensions(Path(save_dir))}
    selected_dimensions: List[DimensionInfo] = [dimensions[dimension_id] for dimension_id in options.dimension_ids if dimension_id in dimensions]

    target_items = _normalize_item_ids(options.item_ids)
    workers = max(1, options.workers or min(os.cpu_count() or 1, 8))

    tasks: List[Tuple[str, str, Sequence[str], Sequence[str], str]] = []
    for dimension in selected_dimensions:
        region_files = [path for path in sorted(dimension.region_dir.glob("r.*.*.mca")) if path.stat().st_size > 0]
        for region_file in region_files:
            tasks.append((str(region_file), dimension.id, tuple(options.target_part_ids), tuple(target_items), options.match_mode))

    if progress:
        progress("scan_started", {"dimensions": [dim.id for dim in selected_dimensions], "region_tasks": len(tasks)})

    matches: List[ScanMatch] = []
    if workers == 1:
        for task in tasks:
            batch, stats, errors = _scan_region_task(task)
            matches.extend(_match_from_dict(match) for match in batch)
            if progress:
                progress("region_done", stats)
            for error in errors:
                if progress:
                    progress("error", {"message": error})
    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(_scan_region_task, task) for task in tasks]
            for future in as_completed(futures):
                batch, stats, errors = future.result()
                matches.extend(_match_from_dict(match) for match in batch)
                if progress:
                    progress("region_done", stats)
                for error in errors:
                    if progress:
                        progress("error", {"message": error})

    matches.sort(key=lambda item: (item.dimension, item.region, item.chunk[1], item.chunk[0], item.x, item.y, item.z, item.part_side or ""))
    if progress:
        progress("scan_finished", {"match_count": len(matches)})
    return matches
