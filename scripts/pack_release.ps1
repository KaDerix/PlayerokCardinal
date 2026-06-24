param(
    [Parameter(Mandatory = $true)]
    [string]$ArchiveName
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$exclude = @(
    ".git", "venv", "venv2", "__pycache__", "logs", "storage",
    "configs", "plugins", "build", "dist", ".idea"
)

$items = Get-ChildItem -Force |
    Where-Object { $exclude -notcontains $_.Name -and $_.Name -notlike "*.zip" }

$dest = Join-Path $root $ArchiveName
if (Test-Path $dest) {
    Remove-Item $dest -Force
}

Compress-Archive -Path $items.FullName -DestinationPath $dest -Force
Write-Host "Packed: $dest"
