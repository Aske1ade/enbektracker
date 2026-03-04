param(
    [switch]$NsisOnly,
    [ValidateSet("local", "server")]
    [string]$Profile = "local",
    [string]$ServerHost = "",
    [string]$ApiBaseUrl = "",
    [string]$ApiBaseUrlDirect = "",
    [string]$WebBaseUrl = ""
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
if ($PSVersionTable.PSVersion.Major -ge 7) {
    $PSNativeCommandUseErrorActionPreference = $true
}

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][scriptblock]$Action
    )

    Write-Host "-> $Name"
    # Avoid stale native exit codes from previous commands.
    $global:LASTEXITCODE = $null
    & $Action
    if (-not $?) {
        throw "Step failed: $Name"
    }
    if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw "Step failed: $Name (exit code: $LASTEXITCODE)"
    }
}

function Stop-AgentProcess {
    $running = Get-Process -Name "desktop-agent" -ErrorAction SilentlyContinue
    if (-not $running) {
        return
    }

    Write-Host "-> Stopping running desktop-agent.exe before build"
    $running | Stop-Process -Force -ErrorAction Stop
    Start-Sleep -Seconds 1
}

function Remove-FileWithRetry {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [int]$Attempts = 5
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    for ($i = 1; $i -le $Attempts; $i++) {
        try {
            Remove-Item -LiteralPath $Path -Force -ErrorAction Stop
            return
        }
        catch {
            if ($i -eq $Attempts) {
                throw "Cannot delete locked file: $Path. Close agent/tray process and retry."
            }
            Start-Sleep -Milliseconds 600
        }
    }
}

function Test-IsLocalOrPrivateHost {
    param(
        [Parameter(Mandatory = $true)][string]$HostValue
    )

    if ($HostValue -match "^(localhost|\[::1\]|127(?:\.\d{1,3}){3}|10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2})(:\d+)?$") {
        return $true
    }

    return $false
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$agentDir = Join-Path $repoRoot "desktop-agent"
$portableExe = Join-Path $agentDir "src-tauri\target\release\desktop-agent.exe"
$nsisPath = Join-Path $agentDir "src-tauri\target\release\bundle\nsis"
$releasePath = Join-Path $agentDir "src-tauri\target\release"

try {
    Invoke-Step -Name "Switch to $agentDir" -Action { Set-Location $agentDir }
    Stop-AgentProcess
    Remove-FileWithRetry -Path $portableExe

    if ($Profile -eq "server") {
        if (-not $WebBaseUrl -and -not $ServerHost) {
            throw "For -Profile server, set -ServerHost (e.g. tracker.example.com) or -WebBaseUrl."
        }
        if (-not $WebBaseUrl -and $ServerHost) {
            if ($ServerHost -match "^https?://") {
                $WebBaseUrl = $ServerHost.TrimEnd("/")
            }
            else {
                $normalizedHost = $ServerHost.TrimEnd("/")
                if (Test-IsLocalOrPrivateHost -HostValue $normalizedHost) {
                    $WebBaseUrl = "http://$normalizedHost"
                }
                else {
                    $WebBaseUrl = "https://$normalizedHost"
                }
            }
        }
        if (-not $ApiBaseUrl) {
            $ApiBaseUrl = "$($WebBaseUrl.TrimEnd('/'))/api/v1"
        }
        if (-not $ApiBaseUrlDirect) {
            $ApiBaseUrlDirect = $ApiBaseUrl
        }
    }
    elseif ($Profile -eq "local") {
        if (-not $WebBaseUrl) {
            $WebBaseUrl = "http://localhost"
        }
        if (-not $ApiBaseUrl) {
            $ApiBaseUrl = "http://localhost/api/v1"
        }
        if (-not $ApiBaseUrlDirect) {
            $ApiBaseUrlDirect = "http://localhost:8888/api/v1"
        }
    }

    Write-Host "-> Build profile: $Profile"

    if ($ApiBaseUrl) {
        $env:ENBEK_AGENT_DEFAULT_API_BASE_URL = $ApiBaseUrl
        Write-Host "-> Using default API URL: $ApiBaseUrl"
    }
    if ($ApiBaseUrlDirect) {
        $env:ENBEK_AGENT_DEFAULT_API_BASE_URL_DIRECT = $ApiBaseUrlDirect
        Write-Host "-> Using direct API URL: $ApiBaseUrlDirect"
    }
    if ($WebBaseUrl) {
        $env:ENBEK_AGENT_DEFAULT_WEB_BASE_URL = $WebBaseUrl
        Write-Host "-> Using default WEB URL: $WebBaseUrl"
    }

    Invoke-Step -Name "npm install" -Action { npm install }
    Invoke-Step -Name "npm run build" -Action { npm run build }

    if ($NsisOnly) {
        Invoke-Step -Name "npm run tauri:build:nsis" -Action { npm run tauri:build:nsis }
    }
    else {
        Invoke-Step -Name "npm run tauri:build" -Action { npm run tauri:build }
    }

    Write-Host ""
    Write-Host "Build completed successfully."
    Write-Host "Installer .exe: $nsisPath"
    Write-Host "Portable binary: $releasePath"
}
catch {
    Write-Error $_
    exit 1
}
