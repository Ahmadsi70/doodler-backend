# Build a Colab-ready zip of Story for export-only workflow (no in-tool render).
# Usage: powershell -File scripts\pack_for_colab.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Desktop = [Environment]::GetFolderPath("Desktop")
$OutZip = Join-Path $Desktop "Story.zip"
$Stage = Join-Path $env:TEMP ("StoryColab_" + [guid]::NewGuid().ToString("N"))

Write-Host "Staging from $Root -> $Stage"
New-Item -ItemType Directory -Path $Stage | Out-Null
robocopy $Root $Stage /E /NFL /NDL /NJH /NJS /nc /ns /np `
  /XD .venv __pycache__ .pytest_cache out remotion\node_modules _audio_src .git `
  /XF *.mp4 *.pyc | Out-Null

if (Test-Path $OutZip) { Remove-Item $OutZip -Force }
Compress-Archive -Path (Join-Path $Stage "*") -DestinationPath $OutZip -Force
Remove-Item $Stage -Recurse -Force
Write-Host "DONE: $OutZip"
Write-Host "Upload this file to Google Drive as MyDrive/Story.zip"
