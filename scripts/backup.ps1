$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$backupDirectory = Join-Path (Get-Location) "data/backups"
New-Item -ItemType Directory -Path $backupDirectory -Force | Out-Null
$backupName = "goldagent-" + (Get-Date -Format "yyyyMMdd-HHmmss") + "-" + ([guid]::NewGuid().ToString("N").Substring(0,8)) + ".dump"
$containerPath = "/tmp/" + $backupName
docker compose exec -T postgres pg_dump -U goldagent -d goldagent --format=custom --file=$containerPath
if ($LASTEXITCODE -ne 0) { throw "pg_dump failed; no valid backup was created" }
$localPath = Join-Path $backupDirectory $backupName
docker compose cp "postgres:$containerPath" $localPath
if ($LASTEXITCODE -ne 0) { throw "Copying backup failed" }
docker compose exec -T postgres pg_restore --list $containerPath | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Backup archive validation failed" }
Write-Output "Backup saved and archive checked: $localPath"
Write-Output "Contains private user data. Keep it outside Git and encrypt backups when appropriate."
