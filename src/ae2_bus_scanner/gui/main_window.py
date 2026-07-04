import json
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List

from ..scanner.dimensions import discover_dimensions
from ..scanner.engine import DEFAULT_PART_IDS, scan_dimensions
from ..scanner.exporters import export_csv, export_json
from ..scanner.models import DimensionInfo, ScanMatch, ScanOptions


class MainWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("AE2 Bus Scanner")
        self.root.geometry("1180x760")

        self.save_var = tk.StringVar()
        self.match_mode_var = tk.StringVar(value="exact")
        self.workers_var = tk.StringVar(value="8")
        self.status_var = tk.StringVar(value="Choose a save folder to begin.")
        self.include_import_var = tk.BooleanVar(value=True)
        self.include_export_var = tk.BooleanVar(value=True)
        self.include_interface_var = tk.BooleanVar(value=True)

        self.dimensions: List[DimensionInfo] = []
        self.dimension_vars: Dict[str, tk.BooleanVar] = {}
        self.matches: List[ScanMatch] = []

        self._build_ui()

    def _build_ui(self):
        top = ttk.Frame(self.root, padding=12)
        top.pack(fill="x")

        ttk.Label(top, text="Save Folder").grid(row=0, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.save_var, width=90).grid(row=1, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(top, text="Browse", command=self.browse_save).grid(row=1, column=1, sticky="ew")
        ttk.Button(top, text="Discover Dimensions", command=self.load_dimensions).grid(row=1, column=2, sticky="ew", padx=(8, 0))
        top.columnconfigure(0, weight=1)

        body = ttk.PanedWindow(self.root, orient="horizontal")
        body.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        left = ttk.Frame(body, padding=8)
        right = ttk.Frame(body, padding=8)
        body.add(left, weight=1)
        body.add(right, weight=3)

        ttk.Label(left, text="Dimensions").pack(anchor="w")
        dim_controls = ttk.Frame(left)
        dim_controls.pack(fill="x", pady=(4, 6))
        ttk.Button(dim_controls, text="All", command=lambda: self.set_all_dimensions(True)).pack(side="left")
        ttk.Button(dim_controls, text="None", command=lambda: self.set_all_dimensions(False)).pack(side="left", padx=(6, 0))

        self.dimension_canvas = tk.Canvas(left, highlightthickness=0)
        self.dimension_scroll = ttk.Scrollbar(left, orient="vertical", command=self.dimension_canvas.yview)
        self.dimension_frame = ttk.Frame(self.dimension_canvas)
        self.dimension_frame.bind("<Configure>", lambda e: self.dimension_canvas.configure(scrollregion=self.dimension_canvas.bbox("all")))
        self.dimension_canvas.create_window((0, 0), window=self.dimension_frame, anchor="nw")
        self.dimension_canvas.configure(yscrollcommand=self.dimension_scroll.set)
        self.dimension_canvas.pack(side="left", fill="both", expand=True)
        self.dimension_scroll.pack(side="right", fill="y")

        filter_frame = ttk.LabelFrame(right, text="Scan Filters", padding=10)
        filter_frame.pack(fill="x")

        device_row = ttk.Frame(filter_frame)
        device_row.pack(fill="x")
        ttk.Checkbutton(device_row, text="Import Bus", variable=self.include_import_var).pack(side="left")
        ttk.Checkbutton(device_row, text="Export Bus", variable=self.include_export_var).pack(side="left", padx=(8, 0))
        ttk.Checkbutton(device_row, text="ME Interface", variable=self.include_interface_var).pack(side="left", padx=(8, 0))

        match_row = ttk.Frame(filter_frame)
        match_row.pack(fill="x", pady=(8, 0))
        ttk.Label(match_row, text="Match Mode").pack(side="left")
        ttk.Combobox(match_row, textvariable=self.match_mode_var, values=["exact", "contains", "all"], state="readonly", width=12).pack(side="left", padx=(8, 16))
        ttk.Label(match_row, text="Workers").pack(side="left")
        ttk.Entry(match_row, textvariable=self.workers_var, width=6).pack(side="left", padx=(8, 0))

        ttk.Label(filter_frame, text="Item IDs (one per line or comma-separated)").pack(anchor="w", pady=(10, 0))
        self.item_text = tk.Text(filter_frame, height=7, wrap="word")
        self.item_text.pack(fill="x", pady=(4, 0))
        ttk.Label(
            filter_frame,
            text="Leave this empty to scan all selected device types.",
        ).pack(anchor="w", pady=(4, 0))

        action_row = ttk.Frame(right)
        action_row.pack(fill="x", pady=(10, 10))
        ttk.Button(action_row, text="Scan", command=self.start_scan).pack(side="left")
        ttk.Button(action_row, text="Export JSON", command=self.export_json_file).pack(side="left", padx=(8, 0))
        ttk.Button(action_row, text="Export CSV", command=self.export_csv_file).pack(side="left", padx=(8, 0))

        self.progress = ttk.Progressbar(right, mode="indeterminate")
        self.progress.pack(fill="x")

        ttk.Label(right, text="Results").pack(anchor="w", pady=(10, 4))
        columns = ("dimension", "pos", "device", "side", "filters", "region", "chunk")
        self.result_tree = ttk.Treeview(right, columns=columns, show="headings", height=20)
        for column, title, width in (
            ("dimension", "Dimension", 150),
            ("pos", "Position", 110),
            ("device", "Device", 160),
            ("side", "Side", 70),
            ("filters", "Filters", 420),
            ("region", "Region", 110),
            ("chunk", "Chunk", 80),
        ):
            self.result_tree.heading(column, text=title)
            self.result_tree.column(column, width=width, anchor="w")
        result_scroll = ttk.Scrollbar(right, orient="vertical", command=self.result_tree.yview)
        self.result_tree.configure(yscrollcommand=result_scroll.set)
        self.result_tree.pack(side="left", fill="both", expand=True)
        result_scroll.pack(side="right", fill="y")

        status = ttk.Label(self.root, textvariable=self.status_var, anchor="w", padding=(12, 0, 12, 12))
        status.pack(fill="x")

    def browse_save(self):
        selected = filedialog.askdirectory(title="Choose Minecraft Save Folder")
        if selected:
            self.save_var.set(selected)

    def load_dimensions(self):
        save_dir = self.save_var.get().strip()
        if not save_dir:
            messagebox.showwarning("Missing Save", "Choose a save folder first.")
            return
        path = Path(save_dir)
        if not path.is_dir():
            messagebox.showerror("Invalid Save", "The selected save folder does not exist.")
            return
        self.dimensions = discover_dimensions(path)
        self.dimension_vars.clear()
        for child in self.dimension_frame.winfo_children():
            child.destroy()
        for dim in self.dimensions:
            var = tk.BooleanVar(value=False)
            self.dimension_vars[dim.id] = var
            text = f"{dim.display_name}  ({dim.region_count} regions, {round(dim.total_bytes / 1024 / 1024, 2)} MB)"
            ttk.Checkbutton(self.dimension_frame, text=text, variable=var).pack(anchor="w", fill="x", pady=2)
        self.status_var.set(f"Discovered {len(self.dimensions)} dimensions.")

    def set_all_dimensions(self, value: bool):
        for var in self.dimension_vars.values():
            var.set(value)

    def _selected_dimensions(self) -> List[str]:
        return [dimension_id for dimension_id, var in self.dimension_vars.items() if var.get()]

    def _selected_parts(self) -> List[str]:
        parts: List[str] = []
        if self.include_import_var.get():
            parts.append("ae2:import_bus")
        if self.include_export_var.get():
            parts.append("ae2:export_bus")
        if self.include_interface_var.get():
            parts.extend(["ae2:cable_interface", "ae2:interface"])
        return parts

    def _item_ids(self) -> List[str]:
        raw = self.item_text.get("1.0", "end").strip()
        if not raw:
            return []
        items: List[str] = []
        for line in raw.replace(",", "\n").splitlines():
            line = line.strip()
            if line:
                items.append(line)
        return items

    def start_scan(self):
        save_dir = self.save_var.get().strip()
        selected_dimensions = self._selected_dimensions()
        selected_parts = self._selected_parts()
        if not save_dir:
            messagebox.showwarning("Missing Save", "Choose a save folder first.")
            return
        if not selected_dimensions:
            messagebox.showwarning("Missing Dimensions", "Select at least one dimension.")
            return
        if not selected_parts:
            messagebox.showwarning("Missing Devices", "Select at least one device type.")
            return

        try:
            workers = max(1, int(self.workers_var.get().strip()))
        except ValueError:
            messagebox.showerror("Invalid Workers", "Workers must be a positive integer.")
            return

        self.progress.start(10)
        item_ids = self._item_ids()
        if item_ids:
            self.status_var.set(f"Scanning for {len(item_ids)} item filter(s)...")
        else:
            self.status_var.set("Scanning all selected device types...")

        options = ScanOptions(
            dimension_ids=selected_dimensions,
            target_part_ids=selected_parts,
            item_ids=item_ids,
            match_mode=self.match_mode_var.get(),
            workers=workers,
        )

        def run_scan():
            try:
                matches = scan_dimensions(Path(save_dir), options, progress=self._thread_progress)
                self.root.after(0, lambda: self._scan_finished(matches))
            except Exception as exc:
                self.root.after(0, lambda: self._scan_failed(exc))

        threading.Thread(target=run_scan, daemon=True).start()

    def _thread_progress(self, event: str, payload: Dict[str, object]):
        if event == "scan_started":
            message = f"Scanning {payload['region_tasks']} region files..."
        elif event == "region_done":
            message = f"Finished {payload['region']} with {payload['matches']} matches"
        elif event == "error":
            message = str(payload["message"])
        elif event == "scan_finished":
            message = f"Scan complete: {payload['match_count']} matches"
        else:
            return
        self.root.after(0, lambda: self.status_var.set(message))

    def _scan_finished(self, matches: List[ScanMatch]):
        self.matches = matches
        self.progress.stop()
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)
        for match in matches:
            filters = ", ".join(filter_item.id for filter_item in match.filters)
            self.result_tree.insert(
                "",
                "end",
                values=(
                    match.dimension,
                    f"{match.x}, {match.y}, {match.z}",
                    match.part_id,
                    match.part_side or "",
                    filters,
                    match.region,
                    f"{match.chunk[0]}, {match.chunk[1]}",
                ),
            )
        self.status_var.set(f"Scan complete: {len(matches)} matches")

    def _scan_failed(self, exc: Exception):
        self.progress.stop()
        self.status_var.set("Scan failed")
        messagebox.showerror("Scan Failed", str(exc))

    def export_json_file(self):
        if not self.matches:
            messagebox.showinfo("No Results", "Run a scan first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        export_json(self.matches, Path(path))
        self.status_var.set(f"Exported JSON to {path}")

    def export_csv_file(self):
        if not self.matches:
            messagebox.showinfo("No Results", "Run a scan first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        export_csv(self.matches, Path(path))
        self.status_var.set(f"Exported CSV to {path}")


def launch():
    root = tk.Tk()
    MainWindow(root)
    root.mainloop()
