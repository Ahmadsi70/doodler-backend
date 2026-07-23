# Setup GitHub remote for Story (run in PowerShell)
# Requires: git + GitHub CLI (https://cli.github.com/) OR manual remote URL

param(
  [string]$RepoName = "Story",
  [switch]$Public
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

if (-not (Test-Path .git)) {
  git init
}

$visibility = if ($Public) { "--public" } else { "--private" }

if (Get-Command gh -ErrorAction SilentlyContinue) {
  gh auth status
  gh repo create $RepoName $visibility --source=. --remote=origin --push
  Write-Host "DONE: remote origin pushed via gh"
} else {
  Write-Host "BLOCKED: gh not installed."
  Write-Host "1) Install https://cli.github.com/  OR create empty repo on GitHub"
  Write-Host "2) git remote add origin https://github.com/<USER>/$RepoName.git"
  Write-Host "3) git push -u origin master"
  exit 1
}
