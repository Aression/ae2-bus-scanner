# AE2 Bus Scanner

Scan Minecraft saves for AE2 import buses, export buses, and interfaces that contain selected filter items.

This project includes:

- a reusable scan engine
- a CLI
- a desktop GUI built with `tkinter`

See `DESIGN.md` for the implementation notes and roadmap.

## Run

GUI:

```powershell
cd .\ae2_bus_scanner
$env:PYTHONPATH = ".\src"
python .\launch_gui.py
```

CLI list dimensions:

```powershell
cd .\ae2_bus_scanner
.\run_cli.ps1 list-dimensions --save "D:\Minecraft\PCL2\.minecraft\versions\Create New Horizon\saves\[CTNH]server-backup"
```

CLI scan example:

```powershell
cd .\ae2_bus_scanner
.\run_cli.ps1 scan `
  --save "D:\Minecraft\PCL2\.minecraft\versions\Create New Horizon\saves\[CTNH]server-backup" `
  --dimension "javd:void" `
  --part "ae2:export_bus" `
  --part "ae2:cable_interface" `
  --match-mode all `
  --workers 8 `
  --json-out ".\void_scan.json"
```
