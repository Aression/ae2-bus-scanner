from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence


@dataclass(frozen=True)
class DimensionInfo:
    id: str
    display_name: str
    region_dir: Path
    region_count: int
    total_bytes: int
    last_modified: float


@dataclass(frozen=True)
class FilterItem:
    id: str
    kind: str = "unknown"
    count: Optional[int] = None
    slot: Optional[int] = None
    tag: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class ScanMatch:
    dimension: str
    region: str
    chunk: List[int]
    x: int
    y: int
    z: int
    block: str
    part_id: str
    part_side: Optional[str]
    filters: List[FilterItem]
    settings: Dict[str, Any] = field(default_factory=dict)
    raw_fields: List[str] = field(default_factory=list)
    part_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension,
            "region": self.region,
            "chunk": self.chunk,
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "block": self.block,
            "part_id": self.part_id,
            "part_side": self.part_side,
            "filters": [
                {
                    "id": item.id,
                    "kind": item.kind,
                    "count": item.count,
                    "slot": item.slot,
                    "tag": item.tag,
                }
                for item in self.filters
            ],
            "settings": self.settings,
            "raw_fields": self.raw_fields,
            "part_data": self.part_data,
        }


@dataclass(frozen=True)
class ScanOptions:
    dimension_ids: Sequence[str]
    target_part_ids: Sequence[str]
    item_ids: Sequence[str] = ()
    match_mode: str = "exact"
    workers: int = 1
    include_settings: bool = True


ProgressCallback = Callable[[str, Dict[str, Any]], None]
