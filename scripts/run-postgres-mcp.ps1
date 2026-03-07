# Load POSTGRES_CONNECTION_STRING from .env in project root
$projectRoot = Split-Path $PSScriptRoot -Parent
$envFile = Join-Path $projectRoot ".env"

if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^POSTGRES_CONNECTION_STRING=(.+)$') {
            $script:connString = $matches[1].Trim().Trim('"').Trim("'")
        }
    }
}

if (-not $script:connString) {
    $script:connString = $env:POSTGRES_CONNECTION_STRING
}

if (-not $script:connString) {
    Write-Error "POSTGRES_CONNECTION_STRING not set. Add it to .env or set the environment variable."
    exit 1
}

& npx -y @henkey/postgres-mcp-server --connection-string $script:connString
