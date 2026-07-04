import csv
import json
from pathlib import Path
from typing import Iterable

from .models import ScanMatch


def export_json(matches: Iterable[ScanMatch], output_path: Path) -> None:
    payload = {"count": 0, "matches": []}
    for match in matches:
        payload["matches"].append(match.to_dict())
    payload["count"] = len(payload["matches"])
    Path(output_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def export_csv(matches: Iterable[ScanMatch], output_path: Path) -> None:
    rows = list(matches)
    with Path(output_path).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "dimension",
                "region",
                "chunk_x",
                "chunk_z",
                "x",
                "y",
                "z",
                "part_id",
                "part_side",
                "filter_ids",
                "filter_kinds",
            ],
        )
        writer.writeheader()
        for match in rows:
            writer.writerow(
                {
                    "dimension": match.dimension,
                    "region": match.region,
                    "chunk_x": match.chunk[0],
                    "chunk_z": match.chunk[1],
                    "x": match.x,
                    "y": match.y,
                    "z": match.z,
                    "part_id": match.part_id,
                    "part_side": match.part_side or "",
                    "filter_ids": "; ".join(item.id for item in match.filters),
                    "filter_kinds": "; ".join(item.kind for item in match.filters),
                }
            )
