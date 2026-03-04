param(
    [string]$BaseUrl = "http://localhost",
    [string]$SuperuserEmail,
    [string]$SuperuserPassword,
    [int]$Cycles = 3,
    [int]$ReadinessTimeoutSeconds = 180,
    [int]$RetryIntervalSeconds = 5,
    [switch]$UseResetDb,
    [switch]$NoAutoRepair
)

if ($Cycles -lt 1) {
    throw "Cycles must be >= 1"
}
if ($ReadinessTimeoutSeconds -lt 10) {
    throw "ReadinessTimeoutSeconds must be >= 10"
}
if ($RetryIntervalSeconds -lt 1) {
    throw "RetryIntervalSeconds must be >= 1"
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$devScript = Join-Path $PSScriptRoot "dev.ps1"
$envFile = Join-Path $repoRoot ".env"
$logsDir = Join-Path $repoRoot "logs"
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$runId = "p0-$timestamp"
$runDir = Join-Path $logsDir $runId
$failureRootDir = Join-Path $runDir "failure"
$logFile = Join-Path $runDir "p0-verify.log"
$summaryJsonFile = Join-Path $runDir "summary.json"
$summaryMdFile = Join-Path $runDir "summary.md"
$composeDevArgs = @(
    "compose",
    "-f", "docker-compose.yml",
    "-f", "docker-compose.override.yml",
    "-f", "docker-compose.dev.yml"
)
$autoRepair = -not $NoAutoRepair

if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir | Out-Null
}
if (-not (Test-Path $runDir)) {
    New-Item -ItemType Directory -Path $runDir | Out-Null
}
if (-not (Test-Path $failureRootDir)) {
    New-Item -ItemType Directory -Path $failureRootDir | Out-Null
}

function Write-Log {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Message,
        [ValidateSet("INFO", "WARN", "ERROR")]
        [string]$Level = "INFO"
    )

    $line = "{0} [{1}] {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Level, $Message
    Write-Host $line
    Add-Content -Path $logFile -Value $line
}

function Get-DotenvValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Key
    )

    if (-not (Test-Path $envFile)) {
        return $null
    }

    $escaped = [regex]::Escape($Key)
    $line = Get-Content $envFile | Where-Object {
        $_ -match "^\s*$escaped\s*="
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

function Invoke-DevCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CommandName
    )

    Write-Log "RUN: dev.ps1 $CommandName"
    $global:LASTEXITCODE = 0
    $ok = $true

    try {
        $output = & $devScript $CommandName 2>&1
        if ($output) {
            $output | Tee-Object -FilePath $logFile -Append | Out-Host
        }
    }
    catch {
        Write-Log "Command dev.ps1 $CommandName threw exception: $($_.Exception.Message)" "ERROR"
        $ok = $false
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Log "Command dev.ps1 $CommandName exit code: $LASTEXITCODE" "ERROR"
        $ok = $false
    }

    if ($ok) {
        Write-Log "OK: dev.ps1 $CommandName"
    }
    return $ok
}

function Restart-ProxyService {
    Write-Log "RUN: docker compose restart proxy"
    $global:LASTEXITCODE = 0
    $ok = $true

    try {
        $output = & docker @composeDevArgs restart proxy 2>&1
        if ($output) {
            $output | Tee-Object -FilePath $logFile -Append | Out-Host
        }
    }
    catch {
        Write-Log "docker compose restart proxy threw exception: $($_.Exception.Message)" "ERROR"
        $ok = $false
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Log "docker compose restart proxy exit code: $LASTEXITCODE" "ERROR"
        $ok = $false
    }

    if ($ok) {
        Write-Log "OK: docker compose restart proxy"
    }
    return $ok
}

function Test-HealthReadiness {
    $uri = "$BaseUrl/api/v1/utils/health-check/"
    try {
        $response = Invoke-WebRequest -Uri $uri -Method Get -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
        $statusCode = [int]$response.StatusCode
        $body = "$($response.Content)".Trim()
        $bodyOk = $false

        if ($body) {
            if ($body -eq "true") {
                $bodyOk = $true
            }
            else {
                try {
                    $parsed = $body | ConvertFrom-Json -ErrorAction Stop
                    if ($parsed -eq $true) {
                        $bodyOk = $true
                    }
                }
                catch {
                    $bodyOk = $false
                }
            }
        }

        return @{
            ok = ($statusCode -eq 200 -and $bodyOk)
            status_code = $statusCode
            body = $body
            error = $null
        }
    }
    catch {
        $statusCode = $null
        try {
            if ($_.Exception.Response) {
                $statusCode = [int]$_.Exception.Response.StatusCode.value__
            }
        }
        catch {}

        return @{
            ok = $false
            status_code = $statusCode
            body = $null
            error = $_.Exception.Message
        }
    }
}

function Test-LoginReadiness {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Email,
        [Parameter(Mandatory = $true)]
        [string]$Password
    )

    $uri = "$BaseUrl/api/v1/auth/access-token"
    $bodyRaw = "username=$([uri]::EscapeDataString($Email))&password=$([uri]::EscapeDataString($Password))"

    try {
        $response = Invoke-WebRequest -Uri $uri -Method Post -ContentType "application/x-www-form-urlencoded" -Body $bodyRaw -TimeoutSec 12 -UseBasicParsing -ErrorAction Stop
        $statusCode = [int]$response.StatusCode
        $content = "$($response.Content)"
        $tokenPresent = $false

        if ($content) {
            try {
                $payload = $content | ConvertFrom-Json -ErrorAction Stop
                if ($payload.access_token) {
                    $tokenPresent = $true
                }
            }
            catch {
                $tokenPresent = $false
            }
        }

        return @{
            ok = ($statusCode -eq 200 -and $tokenPresent)
            status_code = $statusCode
            token_present = $tokenPresent
            body = $content
            error = $null
        }
    }
    catch {
        $statusCode = $null
        try {
            if ($_.Exception.Response) {
                $statusCode = [int]$_.Exception.Response.StatusCode.value__
            }
        }
        catch {}

        return @{
            ok = $false
            status_code = $statusCode
            token_present = $false
            body = $null
            error = $_.Exception.Message
        }
    }
}

function Wait-Readiness {
    param(
        [Parameter(Mandatory = $true)]
        [int]$CycleNumber,
        [Parameter(Mandatory = $true)]
        [string]$Email,
        [Parameter(Mandatory = $true)]
        [string]$Password
    )

    $start = Get-Date
    $deadline = $start.AddSeconds($ReadinessTimeoutSeconds)
    $attempt = 0
    $consecutive404 = 0
    $lastHealth = $null
    $lastLogin = $null

    while ((Get-Date) -lt $deadline) {
        $attempt += 1
        $lastHealth = Test-HealthReadiness

        if ($lastHealth.ok) {
            $lastLogin = Test-LoginReadiness -Email $Email -Password $Password
        }
        else {
            $lastLogin = @{
                ok = $false
                status_code = $null
                token_present = $false
                body = $null
                error = "skipped: health not ready"
            }
        }

        if ($lastHealth.ok -and $lastLogin.ok) {
            $duration = [math]::Round(((Get-Date) - $start).TotalSeconds, 2)
            Write-Log "Cycle $CycleNumber readiness passed on attempt $attempt in ${duration}s"
            return @{
                ok = $true
                attempts = $attempt
                duration_sec = $duration
                failure_reason = $null
                health = $lastHealth
                login = $lastLogin
            }
        }

        if ($lastHealth.status_code -eq 404) {
            $consecutive404 += 1
        }
        else {
            $consecutive404 = 0
        }

        Write-Log ("Cycle {0} readiness attempt {1} failed: health={2}, login={3}" -f $CycleNumber, $attempt, $lastHealth.status_code, $lastLogin.status_code) "WARN"
        if ($lastHealth.error) {
            Write-Log "Cycle $CycleNumber health error: $($lastHealth.error)" "WARN"
        }
        if ($lastLogin.error -and $lastLogin.error -ne "skipped: health not ready") {
            Write-Log "Cycle $CycleNumber login error: $($lastLogin.error)" "WARN"
        }

        if ($consecutive404 -ge 6) {
            $duration = [math]::Round(((Get-Date) - $start).TotalSeconds, 2)
            Write-Log "Cycle $CycleNumber readiness aborted after repeated 404 responses" "WARN"
            return @{
                ok = $false
                attempts = $attempt
                duration_sec = $duration
                failure_reason = "repeated_404"
                health = $lastHealth
                login = $lastLogin
            }
        }

        Start-Sleep -Seconds $RetryIntervalSeconds
    }

    $duration = [math]::Round(((Get-Date) - $start).TotalSeconds, 2)
    Write-Log "Cycle $CycleNumber readiness timed out after ${duration}s" "ERROR"
    return @{
        ok = $false
        attempts = $attempt
        duration_sec = $duration
        failure_reason = "timeout"
        health = $lastHealth
        login = $lastLogin
    }
}

function Get-ComposeServiceLog {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ServiceName,
        [int]$Tail = 300
    )

    try {
        $global:LASTEXITCODE = 0
        $lines = & docker @composeDevArgs logs --no-color --tail=$Tail $ServiceName 2>&1
        if ($LASTEXITCODE -ne 0) {
            return ""
        }
        return ($lines -join [Environment]::NewLine)
    }
    catch {
        return ""
    }
}

function Detect-RepairReason {
    $backendLog = Get-ComposeServiceLog -ServiceName "backend" -Tail 400
    if (-not $backendLog) {
        return $null
    }

    if ($backendLog -match "password authentication failed for user") {
        return "Detected DB password auth failure in backend logs"
    }
    if ($backendLog -match 'relation "user" does not exist') {
        return "Detected missing table 'user' in backend logs"
    }
    if ($backendLog -match "alembic" -and $backendLog -match "failed") {
        return "Detected migration failure signature in backend logs"
    }
    return $null
}

function Test-BackendStartupChain {
    param(
        [int]$Tail = 1200
    )

    $backendLog = Get-ComposeServiceLog -ServiceName "backend" -Tail $Tail
    if (-not $backendLog) {
        return @{
            ok = $false
            missing_token = $null
            error = "Backend logs are unavailable for startup chain check"
        }
    }

    $stages = @(
        @{
            name = "prestart"
            patterns = @("Running script /app/prestart.sh")
        },
        @{
            name = "alembic"
            patterns = @("alembic upgrade", "alembic.runtime.migration")
        },
        @{
            name = "initial_data"
            patterns = @("Initial data created")
        },
        @{
            name = "startup_complete"
            patterns = @("Application startup complete")
        }
    )

    $cursor = 0
    foreach ($stage in $stages) {
        $found = $false
        foreach ($pattern in $stage.patterns) {
            $idx = $backendLog.IndexOf($pattern, $cursor, [System.StringComparison]::OrdinalIgnoreCase)
            if ($idx -ge 0) {
                $cursor = $idx + $pattern.Length
                $found = $true
                break
            }
        }

        if (-not $found) {
            return @{
                ok = $false
                missing_token = ($stage.patterns -join " OR ")
                error = "Missing startup stage '$($stage.name)': $($stage.patterns -join " OR ")"
            }
        }
    }

    return @{
        ok = $true
        missing_token = $null
        error = $null
    }
}

function Save-FailureLogs {
    param(
        [Parameter(Mandatory = $true)]
        [int]$CycleNumber,
        [Parameter(Mandatory = $true)]
        [string]$Reason
    )

    $failureDir = Join-Path $failureRootDir "cycle-$CycleNumber"
    if (-not (Test-Path $failureDir)) {
        New-Item -ItemType Directory -Path $failureDir | Out-Null
    }

    Write-Log "Saving failure logs for cycle $CycleNumber. Reason: $Reason"

    $services = @("backend", "proxy", "db")
    foreach ($service in $services) {
        $target = Join-Path $failureDir "$service.log"
        try {
            $global:LASTEXITCODE = 0
            $content = & docker @composeDevArgs logs --no-color $service 2>&1
            $content | Out-File -FilePath $target -Encoding utf8
            Add-Content -Path $logFile -Value "Saved $service logs to $target"
        }
        catch {
            Add-Content -Path $logFile -Value "Failed to save $service logs: $($_.Exception.Message)"
        }
    }

    return $failureDir
}

function Write-SummaryFiles {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$Summary
    )

    $Summary | ConvertTo-Json -Depth 8 | Out-File -FilePath $summaryJsonFile -Encoding utf8

    $md = New-Object System.Collections.Generic.List[string]
    $md.Add("# P0 Verify Summary")
    $md.Add("")
    $md.Add("- Run ID: $($Summary.run_id)")
    $md.Add("- Status: **$($Summary.status)**")
    $md.Add("- Started: $($Summary.started_at)")
    $md.Add("- Finished: $($Summary.finished_at)")
    $md.Add("- Base URL: $($Summary.base_url)")
    $md.Add("- Cycles: $($Summary.cycles_total)")
    $md.Add("- Artifacts dir: $($Summary.artifacts_dir)")
    $md.Add("- Log file: $($Summary.log_file)")
    $md.Add("")
    $md.Add("| Cycle | Status | Readiness | Reason | Health | Login | Startup Chain | Attempts | Repair | Proxy Restart | Reset DB | Failure Logs |")
    $md.Add("|---|---|---|---|---:|---:|---|---:|---|---|---|---|")

    foreach ($c in $Summary.cycles) {
        $md.Add("| $($c.cycle) | $($c.status) | $($c.readiness_ok) | $($c.readiness_failure_reason) | $($c.health_status_code) | $($c.login_status_code) | $($c.startup_chain_ok) | $($c.readiness_attempts) | $($c.repair_invoked) | $($c.proxy_restart_invoked) | $($c.reset_invoked) | $($c.failure_log_dir) |")
    }

    $md | Out-File -FilePath $summaryMdFile -Encoding utf8
}

Write-Log "P0 verifier started. Run ID: $runId"
Write-Log "Artifacts directory: $runDir"
Write-Log "Log file: $logFile"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Log "Docker CLI not found in PATH. Run this script in Windows PowerShell with Docker Desktop integration." "ERROR"
    exit 2
}

if (-not (Test-Path $devScript)) {
    Write-Log "Missing script: $devScript" "ERROR"
    exit 2
}

if (-not $SuperuserEmail) {
    $SuperuserEmail = Get-DotenvValue -Key "FIRST_SUPERUSER"
}
if (-not $SuperuserEmail) {
    $SuperuserEmail = "admin@example.com"
}

if (-not $SuperuserPassword) {
    $SuperuserPassword = Get-DotenvValue -Key "FIRST_SUPERUSER_PASSWORD"
}

if (-not $SuperuserPassword) {
    Write-Log "FIRST_SUPERUSER_PASSWORD is not set. Pass -SuperuserPassword or define it in .env." "ERROR"
    exit 2
}

$summary = [ordered]@{
    run_id = $runId
    started_at = (Get-Date).ToString("s")
    finished_at = $null
    status = "FAILED"
    base_url = $BaseUrl
    cycles_total = $Cycles
    readiness_timeout_seconds = $ReadinessTimeoutSeconds
    retry_interval_seconds = $RetryIntervalSeconds
    auto_repair = $autoRepair
    use_reset_db = [bool]$UseResetDb
    artifacts_dir = $runDir
    failure_logs_dir = $failureRootDir
    log_file = $logFile
    summary_json = $summaryJsonFile
    summary_md = $summaryMdFile
    cycles = @()
}

if ($UseResetDb) {
    Write-Log "UseResetDb enabled. Running reset-db before cycle loop."
    if (-not (Invoke-DevCommand -CommandName "reset-db")) {
        Write-Log "Pre-run reset-db failed. Stop verifier." "ERROR"
        $summary.finished_at = (Get-Date).ToString("s")
        Write-SummaryFiles -Summary $summary
        exit 1
    }
}

$allPassed = $true

for ($cycle = 1; $cycle -le $Cycles; $cycle++) {
    $cycleStart = Get-Date
    Write-Log "=== Cycle $cycle/$Cycles started ==="

    $cycleReport = [ordered]@{
        cycle = $cycle
        started_at = $cycleStart.ToString("s")
        ended_at = $null
        status = "FAILED"
        down_ok = $false
        up_ok = $false
        readiness_ok = $false
        readiness_attempts = 0
        readiness_duration_sec = 0
        readiness_failure_reason = $null
        health_status_code = $null
        login_status_code = $null
        startup_chain_ok = $false
        startup_chain_error = $null
        startup_chain_missing_token = $null
        doctor_ok = $false
        repair_invoked = $false
        repair_reason = $null
        repair_ok = $null
        proxy_restart_invoked = $false
        proxy_restart_ok = $null
        reset_invoked = $false
        reset_ok = $null
        failure_log_dir = $null
        duration_sec = 0
    }

    $cycleReport.down_ok = Invoke-DevCommand -CommandName "down"
    if ($cycleReport.down_ok) {
        $cycleReport.up_ok = Invoke-DevCommand -CommandName "up"
    }

    $readiness = $null
    if ($cycleReport.down_ok -and $cycleReport.up_ok) {
        $readiness = Wait-Readiness -CycleNumber $cycle -Email $SuperuserEmail -Password $SuperuserPassword
        $cycleReport.readiness_ok = [bool]$readiness.ok
        $cycleReport.readiness_attempts = [int]$readiness.attempts
        $cycleReport.readiness_duration_sec = [double]$readiness.duration_sec
        $cycleReport.readiness_failure_reason = $readiness.failure_reason
        $cycleReport.health_status_code = $readiness.health.status_code
        $cycleReport.login_status_code = $readiness.login.status_code

        if (-not $cycleReport.readiness_ok -and $autoRepair) {
            $reason = Detect-RepairReason
            if ($reason) {
                $cycleReport.repair_invoked = $true
                $cycleReport.repair_reason = $reason
                Write-Log "Cycle $cycle invoking repair-db. Reason: $reason" "WARN"
                $cycleReport.repair_ok = Invoke-DevCommand -CommandName "repair-db"

                if ($cycleReport.repair_ok) {
                    $readinessAfterRepair = Wait-Readiness -CycleNumber $cycle -Email $SuperuserEmail -Password $SuperuserPassword
                    $cycleReport.readiness_ok = [bool]$readinessAfterRepair.ok
                    $cycleReport.readiness_attempts = [int]($cycleReport.readiness_attempts + $readinessAfterRepair.attempts)
                    $cycleReport.readiness_duration_sec = [double]($cycleReport.readiness_duration_sec + $readinessAfterRepair.duration_sec)
                    $cycleReport.readiness_failure_reason = $readinessAfterRepair.failure_reason
                    $cycleReport.health_status_code = $readinessAfterRepair.health.status_code
                    $cycleReport.login_status_code = $readinessAfterRepair.login.status_code
                }
            }

            if (-not $cycleReport.readiness_ok) {
                $cycleReport.proxy_restart_invoked = $true
                Write-Log "Cycle $cycle invoking proxy restart for readiness recovery" "WARN"
                $cycleReport.proxy_restart_ok = Restart-ProxyService

                if ($cycleReport.proxy_restart_ok) {
                    $readinessAfterProxyRestart = Wait-Readiness -CycleNumber $cycle -Email $SuperuserEmail -Password $SuperuserPassword
                    $cycleReport.readiness_ok = [bool]$readinessAfterProxyRestart.ok
                    $cycleReport.readiness_attempts = [int]($cycleReport.readiness_attempts + $readinessAfterProxyRestart.attempts)
                    $cycleReport.readiness_duration_sec = [double]($cycleReport.readiness_duration_sec + $readinessAfterProxyRestart.duration_sec)
                    $cycleReport.readiness_failure_reason = $readinessAfterProxyRestart.failure_reason
                    $cycleReport.health_status_code = $readinessAfterProxyRestart.health.status_code
                    $cycleReport.login_status_code = $readinessAfterProxyRestart.login.status_code
                }
            }

            if (-not $cycleReport.readiness_ok) {
                $cycleReport.reset_invoked = $true
                Write-Log "Cycle $cycle invoking reset-db after unsuccessful readiness recovery" "WARN"
                $cycleReport.reset_ok = Invoke-DevCommand -CommandName "reset-db"

                if ($cycleReport.reset_ok) {
                    $readinessAfterReset = Wait-Readiness -CycleNumber $cycle -Email $SuperuserEmail -Password $SuperuserPassword
                    $cycleReport.readiness_ok = [bool]$readinessAfterReset.ok
                    $cycleReport.readiness_attempts = [int]($cycleReport.readiness_attempts + $readinessAfterReset.attempts)
                    $cycleReport.readiness_duration_sec = [double]($cycleReport.readiness_duration_sec + $readinessAfterReset.duration_sec)
                    $cycleReport.readiness_failure_reason = $readinessAfterReset.failure_reason
                    $cycleReport.health_status_code = $readinessAfterReset.health.status_code
                    $cycleReport.login_status_code = $readinessAfterReset.login.status_code
                }
            }
        }

        if ($cycleReport.readiness_ok) {
            $startupChain = Test-BackendStartupChain
            $cycleReport.startup_chain_ok = [bool]$startupChain.ok
            $cycleReport.startup_chain_error = $startupChain.error
            $cycleReport.startup_chain_missing_token = $startupChain.missing_token

            if ($cycleReport.startup_chain_ok) {
                Write-Log "Cycle $cycle startup chain check passed"
            }
            else {
                Write-Log "Cycle $cycle startup chain check failed: $($cycleReport.startup_chain_error)" "ERROR"
            }
        }

        $cycleReport.doctor_ok = Invoke-DevCommand -CommandName "doctor"
    }

    if ($cycleReport.down_ok -and $cycleReport.up_ok -and $cycleReport.readiness_ok -and $cycleReport.startup_chain_ok -and $cycleReport.doctor_ok) {
        $cycleReport.status = "PASSED"
        Write-Log "=== Cycle $cycle PASSED ==="
    }
    else {
        $allPassed = $false
        $failureReason = "down=$($cycleReport.down_ok), up=$($cycleReport.up_ok), readiness=$($cycleReport.readiness_ok), startup_chain=$($cycleReport.startup_chain_ok), doctor=$($cycleReport.doctor_ok)"
        $cycleReport.failure_log_dir = Save-FailureLogs -CycleNumber $cycle -Reason $failureReason
        Write-Log "=== Cycle $cycle FAILED ===" "ERROR"
    }

    $cycleEnd = Get-Date
    $cycleReport.ended_at = $cycleEnd.ToString("s")
    $cycleReport.duration_sec = [math]::Round(($cycleEnd - $cycleStart).TotalSeconds, 2)
    $summary.cycles += $cycleReport
}

$summary.status = if ($allPassed) { "PASSED" } else { "FAILED" }
$summary.finished_at = (Get-Date).ToString("s")
Write-SummaryFiles -Summary $summary

Write-Log "P0 verifier completed with status: $($summary.status)"
Write-Log "Summary JSON: $summaryJsonFile"
Write-Log "Summary MD: $summaryMdFile"

if ($allPassed) {
    exit 0
}
exit 1
