$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$env:PYTHONPATH = Join-Path $root "src"

python -m PyInstaller `
  --noconfirm `
  --clean `
  --name AE2BusScanner `
  --windowed `
  --onefile `
  --paths (Join-Path $root "src") `
  --hidden-import anvil `
  --hidden-import nbt `
  --collect-data anvil `
  --collect-submodules ae2_bus_scanner `
  .\launch_gui.py
