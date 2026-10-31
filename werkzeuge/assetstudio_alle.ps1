# Exportiert mit AssetStudioMod alle Galerie-Digimon als FBX (Modell + Skelett + Texturen).
# Die Animationen holt danach anim_export.py – hier werden sie übersprungen.
# Ändert nichts am Spiel. Aufruf: powershell -ExecutionPolicy Bypass -File assetstudio_alle.ps1
$base = Split-Path $PSScriptRoot -Parent
$exe  = (Get-ChildItem (Join-Path $base "_extern\AssetStudioModCLI") -Recurse -Filter "AssetStudioModCLI.exe" | Select-Object -First 1).FullName
if (-not $exe) { Write-Host "AssetStudioMod fehlt - erst assetstudio_holen.ps1 starten."; exit 1 }
$ids = (Get-Content (Join-Path $PSScriptRoot "galerie_ids.txt")) -split '\s+' | Where-Object { $_ }
$i = 0
foreach ($id in $ids) {
  $i++
  $in  = Join-Path $base "_spieldaten\export_in\$id"
  $out = Join-Path $base "_spieldaten\export\$id"
  if (Get-ChildItem $out -Recurse -Filter "*.fbx" -ErrorAction SilentlyContinue) { Write-Host "[$i/$($ids.Count)] $id schon da"; continue }
  New-Item -ItemType Directory -Force $out | Out-Null
  Write-Host "[$i/$($ids.Count)] $id ..."
  & $exe $in -m animator -o $out --fbx-animation skip *> (Join-Path $out "protokoll.txt")
}
$fbx = (Get-ChildItem (Join-Path $base "_spieldaten\export") -Recurse -Filter "*.fbx").Count
Write-Host "Fertig: $fbx FBX-Dateien"
