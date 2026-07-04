from pathlib import Path
from typing import List

from .models import DimensionInfo


def _region_files(region_dir: Path):
    return [path for path in sorted(region_dir.glob("r.*.*.mca")) if path.stat().st_size > 0]


def _build_dimension_info(dimension_id: str, display_name: str, region_dir: Path) -> DimensionInfo:
    region_files = _region_files(region_dir)
    total_bytes = sum(path.stat().st_size for path in region_files)
    last_modified = max((path.stat().st_mtime for path in region_files), default=0.0)
    return DimensionInfo(
        id=dimension_id,
        display_name=display_name,
        region_dir=region_dir,
        region_count=len(region_files),
        total_bytes=total_bytes,
        last_modified=last_modified,
    )


def discover_dimensions(save_dir: Path) -> List[DimensionInfo]:
    save_dir = Path(save_dir)
    found: List[DimensionInfo] = []

    overworld = save_dir / "region"
    if overworld.is_dir():
        found.append(_build_dimension_info("minecraft:overworld", "minecraft:overworld", overworld))

    nether = save_dir / "DIM-1" / "region"
    if nether.is_dir():
        found.append(_build_dimension_info("minecraft:the_nether", "minecraft:the_nether", nether))

    the_end = save_dir / "DIM1" / "region"
    if the_end.is_dir():
        found.append(_build_dimension_info("minecraft:the_end", "minecraft:the_end", the_end))

    dimensions_root = save_dir / "dimensions"
    if dimensions_root.is_dir():
        for namespace_dir in sorted(path for path in dimensions_root.iterdir() if path.is_dir()):
            for region_dir in sorted(namespace_dir.rglob("region")):
                relative = region_dir.relative_to(dimensions_root)
                parts = relative.parts
                if len(parts) < 3:
                    continue
                namespace = parts[0]
                dim_path = "/".join(parts[1:-1])
                dimension_id = f"{namespace}:{dim_path}"
                found.append(_build_dimension_info(dimension_id, dimension_id, region_dir))

    found.sort(key=lambda item: item.display_name)
    return found
