param(
    [Parameter(Mandatory = $true)]
    [ValidateSet(
        "up",
        "down",
        "status",
        "doctor",
        "migrate",
        "repair-db",
        "reset-db",
        "watch",
        "logs-backend",
        "logs-proxy",
        "logs-frontend",
        "sync-db-password",
        "test-backend",
        "test-frontend",
        "lint"
    )]
    [string]$Command
)

$composeDev = @(
    "-f", "docker-compose.yml",
    "-f", "docker-compose.override.yml",
    "-f", "docker-compose.dev.yml"
)

function Get-DotenvValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Key
    )

    $line = Get-Content ".env" | Where-Object {
        $_ -match "^\s*$Key="
    } | Select-Object -First 1

    if (-not $line) {
        return $null
    }

    $value = ($line -split "=", 2)[1].Trim()
    if (
        ($value.StartsWith('"') -and $value.EndsWith('"')) -or
        ($value.StartsWith("'") -and $value.EndsWith("'"))
    ) {
        return $value.Substring(1, $value.Length - 2)
    }
    return $value
}

function Sync-DbPassword {
    $postgresUser = Get-DotenvValue -Key "POSTGRES_USER"
    if (-not $postgresUser) {
        $postgresUser = "postgres"
    }
    $postgresPassword = Get-DotenvValue -Key "POSTGRES_PASSWORD"
    if (-not $postgresPassword) {
        throw "POSTGRES_PASSWORD not found in .env"
    }
    $escapedPassword = $postgresPassword.Replace("'", "''")
    docker compose @composeDev exec db psql -U postgres -d postgres -c "ALTER USER $postgresUser WITH PASSWORD '$escapedPassword';"
}

function Sync-AdminUser {
    docker compose @composeDev exec backend python /app/app/sync_superuser.py
}

function Get-HttpStatus {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url
    )

    try {
        return (curl.exe -s -o NUL -w "%{http_code}" "$Url")
    }
    catch {
        return "ERR"
    }
}

function Get-LoginStatus {
    $adminEmail = Get-DotenvValue -Key "FIRST_SUPERUSER"
    if (-not $adminEmail) {
        $adminEmail = "admin@example.com"
    }
    $adminPassword = Get-DotenvValue -Key "FIRST_SUPERUSER_PASSWORD"
    if (-not $adminPassword) {
        return "NO_PASSWORD"
    }

    $data = "username=$([uri]::EscapeDataString($adminEmail))&password=$([uri]::EscapeDataString($adminPassword))"
    try {
        return (
            curl.exe -s -o NUL -w "%{http_code}" `
                -X POST "http://localhost/api/v1/auth/access-token" `
                -H "Content-Type: application/x-www-form-urlencoded" `
                -d "$data"
        )
    }
    catch {
        return "ERR"
    }
}

switch ($Command) {
    "up" {
        docker compose @composeDev up -d --build
    }
    "down" {
        docker compose @composeDev down
    }
    "status" {
        docker compose @composeDev ps
        Write-Host ""
        Write-Host "HTTP checks:"
        Write-Host "  frontend (proxy)    http://localhost/                         -> $(Get-HttpStatus -Url "http://localhost/")"
        Write-Host "  backend docs         http://localhost/docs                     -> $(Get-HttpStatus -Url "http://localhost/docs")"
        Write-Host "  backend health       http://localhost/api/v1/utils/health-check/ -> $(Get-HttpStatus -Url "http://localhost/api/v1/utils/health-check/")"
        Write-Host "  backend login        POST /api/v1/auth/access-token           -> $(Get-LoginStatus)"
        Write-Host "  frontend dev (vite)  http://localhost:5173/                   -> $(Get-HttpStatus -Url "http://localhost:5173/")"
        Write-Host ""
        Write-Host "Open URLs:"
        Write-Host "  Frontend (proxy):    http://localhost/"
        Write-Host "  Swagger:             http://localhost/docs"
        Write-Host "  Backend OpenAPI:     http://localhost/api/v1/openapi.json"
        Write-Host "  Frontend dev (HMR):  http://localhost:5173/"
        Write-Host "  Traefik dashboard:   http://localhost:8090/dashboard/"
    }
    "doctor" {
        docker compose @composeDev ps
        docker compose @composeDev logs --tail=80 backend
        docker compose @composeDev logs --tail=80 db
        try {
            $healthCode = curl.exe -s -o NUL -w "%{http_code}" "http://localhost/api/v1/utils/health-check/"
            Write-Host "health-check status: $healthCode"
        }
        catch {
            Write-Host "health-check failed"
        }
    }
    "migrate" {
        docker compose @composeDev exec backend alembic upgrade head
    }
    "repair-db" {
        Sync-DbPassword
        docker compose @composeDev exec backend alembic upgrade head
        docker compose @composeDev exec backend python /app/app/init_storage.py
        docker compose @composeDev exec backend python /app/app/initial_data.py
        Sync-AdminUser
        docker compose @composeDev restart backend
    }
    "reset-db" {
        docker compose @composeDev down -v --remove-orphans
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
        docker compose @composeDev up -d --build
    }
    "watch" {
        docker compose @composeDev watch
    }
    "logs-backend" {
        docker compose @composeDev logs -f backend
    }
    "logs-proxy" {
        docker compose @composeDev logs -f proxy
    }
    "logs-frontend" {
        docker compose @composeDev logs -f frontend-dev
    }
    "sync-db-password" {
        Sync-DbPassword
    }
    "test-backend" {
        docker compose @composeDev exec backend bash /app/scripts/test.sh
    }
    "test-frontend" {
        docker compose @composeDev exec frontend-dev npm run build
    }
    "lint" {
        docker compose @composeDev exec backend bash /app/scripts/lint.sh
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
        docker compose @composeDev exec frontend-dev npm run lint
    }
}
