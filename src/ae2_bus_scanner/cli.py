import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import List

from .scanner.dimensions import discover_dimensions
from .scanner.engine import DEFAULT_PART_IDS, scan_dimensions
from .scanner.exporters import export_csv, export_json
from .scanner.models import ScanOptions


def _format_size(num_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(num_bytes)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f}{unit}"
        value /= 1024
    return f"{value:.1f}GB"


def _split_items(raw: List[str]) -> List[str]:
    items: List[str] = []
    for value in raw:
        for part in value.replace(",", "\n").splitlines():
            part = part.strip()
            if part:
                items.append(part)
    return items


def _progress(event: str, payload):
    if event == "scan_started":
        print(f"Scanning {len(payload['dimensions'])} dimensions across {payload['region_tasks']} region files...")
    elif event == "region_done":
        print(f"Finished {payload['region']}: {payload['matches']} matches")
    elif event == "error":
        print(payload["message"])
    elif event == "scan_finished":
        print(f"Scan complete: {payload['match_count']} matches")


def command_list_dimensions(args) -> int:
    dimensions = discover_dimensions(Path(args.save))
    if args.json:
        payload = [
            {
                "id": dim.id,
                "display_name": dim.display_name,
                "region_dir": str(dim.region_dir),
                "region_count": dim.region_count,
                "total_bytes": dim.total_bytes,
                "last_modified": dim.last_modified,
            }
            for dim in dimensions
        ]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    for dim in dimensions:
        modified = datetime.fromtimestamp(dim.last_modified).strftime("%Y-%m-%d %H:%M:%S") if dim.last_modified else "-"
        print(f"{dim.id:30}  regions={dim.region_count:4}  size={_format_size(dim.total_bytes):>8}  modified={modified}")
    return 0


def command_scan(args) -> int:
    items = _split_items(args.item or [])
    target_parts = args.part or sorted(DEFAULT_PART_IDS | {"ae2:interface"})
    options = ScanOptions(
        dimension_ids=args.dimension,
        target_part_ids=target_parts,
        item_ids=items,
        match_mode=args.match_mode,
        workers=args.workers,
    )
    matches = scan_dimensions(Path(args.save), options, progress=_progress)

    if args.json_out:
        export_json(matches, Path(args.json_out))
    if args.csv_out:
        export_csv(matches, Path(args.csv_out))

    if not args.json_out and not args.csv_out:
        payload = {"count": len(matches), "matches": [match.to_dict() for match in matches]}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ae2-bus-scanner", description="Scan Minecraft saves for AE2 buses and interfaces")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list-dimensions", help="List dimensions in a save")
    list_parser.add_argument("--save", required=True, help="Path to the Minecraft save directory")
    list_parser.add_argument("--json", action="store_true", help="Print dimension info as JSON")
    list_parser.set_defaults(func=command_list_dimensions)

    scan_parser = subparsers.add_parser("scan", help="Scan selected dimensions")
    scan_parser.add_argument("--save", required=True, help="Path to the Minecraft save directory")
    scan_parser.add_argument("--dimension", action="append", required=True, help="Dimension ID to scan, can be passed more than once")
    scan_parser.add_argument("--part", action="append", help="Target part ID, can be passed more than once")
    scan_parser.add_argument("--item", action="append", help="Filter item ID, can be passed more than once; leave empty to scan all selected devices")
    scan_parser.add_argument("--match-mode", choices=["exact", "contains", "all"], default="exact")
    scan_parser.add_argument("--workers", type=int, default=min(8, 4))
    scan_parser.add_argument("--json-out", help="Write JSON results to this file")
    scan_parser.add_argument("--csv-out", help="Write CSV results to this file")
    scan_parser.set_defaults(func=command_scan)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
