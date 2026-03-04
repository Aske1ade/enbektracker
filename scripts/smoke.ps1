param(
    [string]$BaseUrl = "http://localhost",
    [string]$AdminEmail,
    [string]$AdminPassword
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $repoRoot ".env"
$logsRoot = Join-Path $repoRoot "logs"
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$runId = "smoke-$timestamp"
$runDir = Join-Path $logsRoot $runId
$failureDir = Join-Path $runDir "failure"
$responsesDir = Join-Path $runDir "responses"
$logFile = Join-Path $runDir "smoke.log"
$summaryJsonFile = Join-Path $runDir "summary.json"
$summaryMdFile = Join-Path $runDir "summary.md"

$api = "$BaseUrl/api/v1"
$startedAt = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$status = "PASSED"
$failReason = $null

$steps = New-Object System.Collections.Generic.List[object]
$ids = [ordered]@{}

foreach ($dir in @($logsRoot, $runDir, $failureDir, $responsesDir)) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir | Out-Null
    }
}

if (Test-Path $logFile) {
    Remove-Item $logFile -Force
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

function Get-Excerpt {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Text,
        [int]$MaxLength = 220
    )

    if (-not $Text) {
        return ""
    }

    $flat = ($Text -replace "[\r\n\t]+", " ").Trim()
    if ($flat.Length -le $MaxLength) {
        return $flat
    }

    return $flat.Substring(0, $MaxLength)
}

function Add-Step {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Step,
        [Parameter(Mandatory = $true)]
        [string]$HttpCode,
        [Parameter(Mandatory = $true)]
        [ValidateSet("PASSED", "FAILED")]
        [string]$StepStatus,
        [Parameter(Mandatory = $true)]
        [string]$Note,
        [Parameter(Mandatory = $true)]
        [string]$ResponseFile
    )

    $steps.Add([ordered]@{
        step = $Step
        http_code = $HttpCode
        status = $StepStatus
        note = $Note
        response_file = $ResponseFile
    })
}

function Save-FailureArtifact {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Step,
        [Parameter(Mandatory = $true)]
        [string]$BodyFile,
        [string]$HeadersFile
    )

    if (Test-Path $BodyFile) {
        Copy-Item $BodyFile (Join-Path $failureDir "$Step.body") -Force
    }
    if ($HeadersFile -and (Test-Path $HeadersFile)) {
        Copy-Item $HeadersFile (Join-Path $failureDir "$Step.headers") -Force
    }
}

function Invoke-ApiRequest {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Step,
        [Parameter(Mandatory = $true)]
        [string]$Method,
        [Parameter(Mandatory = $true)]
        [string]$Uri,
        [hashtable]$Headers,
        [object]$Body,
        [string]$ContentType = "application/json"
    )

    $bodyFile = Join-Path $responsesDir "$Step.body"
    $content = ""
    $statusCode = $null

    try {
        $invokeParams = @{
            Uri = $Uri
            Method = $Method
            TimeoutSec = 30
            UseBasicParsing = $true
            ErrorAction = "Stop"
        }

        if ($Headers) {
            $invokeParams["Headers"] = $Headers
        }

        if ($null -ne $Body) {
            if ($ContentType -eq "application/json") {
                $invokeParams["Body"] = ($Body | ConvertTo-Json -Compress -Depth 12)
            }
            else {
                $invokeParams["Body"] = $Body
            }
            $invokeParams["ContentType"] = $ContentType
        }

        $response = Invoke-WebRequest @invokeParams
        $statusCode = [int]$response.StatusCode
        $content = "{0}" -f $response.Content
    }
    catch {
        $statusCode = $null
        $content = ""

        try {
            if ($_.Exception.Response) {
                $statusCode = [int]$_.Exception.Response.StatusCode.value__
                $stream = $_.Exception.Response.GetResponseStream()
                if ($stream) {
                    $reader = New-Object System.IO.StreamReader($stream)
                    $content = $reader.ReadToEnd()
                    $reader.Dispose()
                    $stream.Dispose()
                }
            }
        }
        catch {}

        if (-not $statusCode) {
            throw
        }
    }

    Set-Content -Path $bodyFile -Value $content -NoNewline

    return [ordered]@{
        status_code = "$statusCode"
        body = $content
        body_file = $bodyFile
    }
}

function Assert-200 {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Step,
        [Parameter(Mandatory = $true)]
        [hashtable]$Result
    )

    if ($Result.status_code -ne "200") {
        $excerpt = Get-Excerpt -Text $Result.body
        Save-FailureArtifact -Step $Step -BodyFile $Result.body_file
        Add-Step -Step $Step -HttpCode $Result.status_code -StepStatus "FAILED" -Note "Expected 200; body: $excerpt" -ResponseFile ("responses/{0}.body" -f $Step)
        throw "$Step returned HTTP $($Result.status_code), expected 200"
    }
}

function Parse-JsonBody {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Body,
        [Parameter(Mandatory = $true)]
        [string]$Step
    )

    try {
        if ([string]::IsNullOrWhiteSpace($Body)) {
            throw "empty body"
        }
        return $Body | ConvertFrom-Json -Depth 20
    }
    catch {
        throw "$Step returned non-JSON body"
    }
}

function Complete-And-WriteSummary {
    $finishedAt = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

    $failureFiles = Get-ChildItem -Path $failureDir -File -ErrorAction SilentlyContinue
    if (-not $failureFiles) {
        Set-Content -Path (Join-Path $failureDir "no-failures.txt") -Value "No failures captured for run $runId"
    }

    $summary = [ordered]@{
        run_id = $runId
        status = $status
        started_at = $startedAt
        finished_at = $finishedAt
        base_url = $BaseUrl
        artifacts_dir = (Resolve-Path $runDir).Path
        log_file = (Resolve-Path $logFile).Path
        summary_json = $summaryJsonFile
        summary_md = $summaryMdFile
        failure_dir = (Resolve-Path $failureDir).Path
        fail_reason = $failReason
        steps = $steps
        ids = $ids
    }

    $summary | ConvertTo-Json -Depth 12 | Set-Content -Path $summaryJsonFile

    $mdLines = @(
        "# Smoke Summary",
        "",
        "- Run ID: $runId",
        "- Status: **$status**",
        "- Started: $startedAt",
        "- Finished: $finishedAt",
        "- Base URL: $BaseUrl",
        "- Artifacts dir: $((Resolve-Path $runDir).Path)",
        "- Log file: $((Resolve-Path $logFile).Path)"
    )

    if ($failReason) {
        $mdLines += "- Fail reason: $failReason"
    }

    $mdLines += ""
    $mdLines += "| Step | HTTP | Status | Note | Response |"
    $mdLines += "|---|---:|---|---|---|"

    foreach ($step in $steps) {
        $mdLines += "| $($step.step) | $($step.http_code) | $($step.status) | $($step.note) | $($step.response_file) |"
    }

    if ($ids.Count -gt 0) {
        $mdLines += ""
        $mdLines += "## IDs"
        $mdLines += ""
        foreach ($key in $ids.Keys) {
            $mdLines += "- $key: $($ids[$key])"
        }
    }

    Set-Content -Path $summaryMdFile -Value ($mdLines -join [Environment]::NewLine)
}

try {
    if (-not $AdminEmail) {
        $AdminEmail = Get-DotenvValue -Key "FIRST_SUPERUSER"
    }
    if (-not $AdminPassword) {
        $AdminPassword = Get-DotenvValue -Key "FIRST_SUPERUSER_PASSWORD"
    }

    if (-not $AdminEmail -or -not $AdminPassword) {
        throw "Missing admin credentials (AdminEmail/AdminPassword or FIRST_SUPERUSER/FIRST_SUPERUSER_PASSWORD in .env)"
    }

    $runTag = (Get-Date -Format "yyyyMMddHHmmss") + (Get-Random -Minimum 1000 -Maximum 9999)
    $departmentCode = "ENGSMK" + $runTag.Substring($runTag.Length - 6)
    $executorEmail = "smoke.executor.$runTag@example.com"
    $controllerEmail = "smoke.controller.$runTag@example.com"
    $commonPassword = "StrongPass123!"

    Write-Log "Run ID: $runId"
    Write-Log "Base URL: $BaseUrl"

    # 1) Login
    $loginResult = Invoke-ApiRequest -Step "01_login" -Method "Post" -Uri "$api/auth/access-token" -Body "username=$([uri]::EscapeDataString($AdminEmail))&password=$([uri]::EscapeDataString($AdminPassword))" -ContentType "application/x-www-form-urlencoded"
    Assert-200 -Step "01_login" -Result $loginResult
    $loginBody = Parse-JsonBody -Body $loginResult.body -Step "01_login"
    if (-not $loginBody.access_token) {
        Save-FailureArtifact -Step "01_login" -BodyFile $loginResult.body_file
        Add-Step -Step "01_login" -HttpCode $loginResult.status_code -StepStatus "FAILED" -Note "Missing access_token" -ResponseFile "responses/01_login.body"
        throw "01_login missing access_token"
    }
    $token = "$($loginBody.access_token)"
    Add-Step -Step "01_login" -HttpCode $loginResult.status_code -StepStatus "PASSED" -Note "access_token received" -ResponseFile "responses/01_login.body"

    $authHeaders = @{ Authorization = "Bearer $token" }

    # 2) Create department
    $depResult = Invoke-ApiRequest -Step "02_create_department" -Method "Post" -Uri "$api/departments/" -Headers $authHeaders -Body @{
        name = "Engineering Smoke $runTag"
        code = $departmentCode
        description = "Smoke department $runTag"
    }
    Assert-200 -Step "02_create_department" -Result $depResult
    $depBody = Parse-JsonBody -Body $depResult.body -Step "02_create_department"
    if (-not $depBody.id) {
        Save-FailureArtifact -Step "02_create_department" -BodyFile $depResult.body_file
        Add-Step -Step "02_create_department" -HttpCode $depResult.status_code -StepStatus "FAILED" -Note "Missing id" -ResponseFile "responses/02_create_department.body"
        throw "02_create_department missing id"
    }
    $departmentId = [int]$depBody.id
    $ids["DEPARTMENT_ID"] = "$departmentId"
    Add-Step -Step "02_create_department" -HttpCode $depResult.status_code -StepStatus "PASSED" -Note "department_id=$departmentId" -ResponseFile "responses/02_create_department.body"

    # 3) Create project
    $projectResult = Invoke-ApiRequest -Step "03_create_project" -Method "Post" -Uri "$api/projects/" -Headers $authHeaders -Body @{
        name = "Smoke Project $runTag"
        description = "Golden path project"
        department_id = $departmentId
        require_close_comment = $true
        require_close_attachment = $true
        deadline_yellow_days = 3
        deadline_normal_days = 5
    }
    Assert-200 -Step "03_create_project" -Result $projectResult
    $projectBody = Parse-JsonBody -Body $projectResult.body -Step "03_create_project"
    if (-not $projectBody.id) {
        Save-FailureArtifact -Step "03_create_project" -BodyFile $projectResult.body_file
        Add-Step -Step "03_create_project" -HttpCode $projectResult.status_code -StepStatus "FAILED" -Note "Missing id" -ResponseFile "responses/03_create_project.body"
        throw "03_create_project missing id"
    }
    $projectId = [int]$projectBody.id
    $ids["PROJECT_ID"] = "$projectId"
    Add-Step -Step "03_create_project" -HttpCode $projectResult.status_code -StepStatus "PASSED" -Note "project_id=$projectId" -ResponseFile "responses/03_create_project.body"

    # 4) Statuses
    $statusesResult = Invoke-ApiRequest -Step "04_project_statuses" -Method "Get" -Uri "$api/project-statuses/?project_id=$projectId" -Headers $authHeaders
    Assert-200 -Step "04_project_statuses" -Result $statusesResult
    $statusesBody = Parse-JsonBody -Body $statusesResult.body -Step "04_project_statuses"
    $statusItems = @($statusesBody.data)
    if ($statusItems.Count -lt 4) {
        Save-FailureArtifact -Step "04_project_statuses" -BodyFile $statusesResult.body_file
        Add-Step -Step "04_project_statuses" -HttpCode $statusesResult.status_code -StepStatus "FAILED" -Note "count < 4" -ResponseFile "responses/04_project_statuses.body"
        throw "04_project_statuses expected at least 4 statuses"
    }
    $codes = @($statusItems | ForEach-Object { $_.code })
    foreach ($required in @("new", "in_progress", "blocked", "done")) {
        if (-not ($codes -contains $required)) {
            Save-FailureArtifact -Step "04_project_statuses" -BodyFile $statusesResult.body_file
            Add-Step -Step "04_project_statuses" -HttpCode $statusesResult.status_code -StepStatus "FAILED" -Note "missing status code '$required'" -ResponseFile "responses/04_project_statuses.body"
            throw "04_project_statuses missing code $required"
        }
    }

    $statusNewId = [int](($statusItems | Where-Object { $_.code -eq "new" } | Select-Object -First 1).id)
    $statusInProgressId = [int](($statusItems | Where-Object { $_.code -eq "in_progress" } | Select-Object -First 1).id)
    $ids["STATUS_NEW_ID"] = "$statusNewId"
    $ids["STATUS_IN_PROGRESS_ID"] = "$statusInProgressId"
    Add-Step -Step "04_project_statuses" -HttpCode $statusesResult.status_code -StepStatus "PASSED" -Note "statuses ok; new=$statusNewId in_progress=$statusInProgressId" -ResponseFile "responses/04_project_statuses.body"

    # 5a) Executor
    $executorResult = Invoke-ApiRequest -Step "05a_create_executor" -Method "Post" -Uri "$api/users/" -Headers $authHeaders -Body @{
        email = $executorEmail
        password = $commonPassword
        is_active = $true
        is_superuser = $false
        system_role = "executor"
    }
    Assert-200 -Step "05a_create_executor" -Result $executorResult
    $executorBody = Parse-JsonBody -Body $executorResult.body -Step "05a_create_executor"
    if (-not $executorBody.id) {
        Save-FailureArtifact -Step "05a_create_executor" -BodyFile $executorResult.body_file
        Add-Step -Step "05a_create_executor" -HttpCode $executorResult.status_code -StepStatus "FAILED" -Note "Missing id" -ResponseFile "responses/05a_create_executor.body"
        throw "05a_create_executor missing id"
    }
    $executorId = [int]$executorBody.id
    $ids["EXECUTOR_ID"] = "$executorId"
    Add-Step -Step "05a_create_executor" -HttpCode $executorResult.status_code -StepStatus "PASSED" -Note "executor_id=$executorId" -ResponseFile "responses/05a_create_executor.body"

    # 5b) Controller
    $controllerResult = Invoke-ApiRequest -Step "05b_create_controller" -Method "Post" -Uri "$api/users/" -Headers $authHeaders -Body @{
        email = $controllerEmail
        password = $commonPassword
        is_active = $true
        is_superuser = $false
        system_role = "controller"
    }
    Assert-200 -Step "05b_create_controller" -Result $controllerResult
    $controllerBody = Parse-JsonBody -Body $controllerResult.body -Step "05b_create_controller"
    if (-not $controllerBody.id) {
        Save-FailureArtifact -Step "05b_create_controller" -BodyFile $controllerResult.body_file
        Add-Step -Step "05b_create_controller" -HttpCode $controllerResult.status_code -StepStatus "FAILED" -Note "Missing id" -ResponseFile "responses/05b_create_controller.body"
        throw "05b_create_controller missing id"
    }
    $controllerId = [int]$controllerBody.id
    $ids["CONTROLLER_ID"] = "$controllerId"
    Add-Step -Step "05b_create_controller" -HttpCode $controllerResult.status_code -StepStatus "PASSED" -Note "controller_id=$controllerId" -ResponseFile "responses/05b_create_controller.body"

    # 6a) Add executor membership
    $memberExecResult = Invoke-ApiRequest -Step "06a_add_executor_member" -Method "Post" -Uri "$api/projects/$projectId/members" -Headers $authHeaders -Body @{
        project_id = $projectId
        user_id = $executorId
        role = "executor"
        is_active = $true
    }
    Assert-200 -Step "06a_add_executor_member" -Result $memberExecResult
    Add-Step -Step "06a_add_executor_member" -HttpCode $memberExecResult.status_code -StepStatus "PASSED" -Note "executor member added" -ResponseFile "responses/06a_add_executor_member.body"

    # 6b) Add controller membership
    $memberCtrlResult = Invoke-ApiRequest -Step "06b_add_controller_member" -Method "Post" -Uri "$api/projects/$projectId/members" -Headers $authHeaders -Body @{
        project_id = $projectId
        user_id = $controllerId
        role = "controller"
        is_active = $true
    }
    Assert-200 -Step "06b_add_controller_member" -Result $memberCtrlResult
    Add-Step -Step "06b_add_controller_member" -HttpCode $memberCtrlResult.status_code -StepStatus "PASSED" -Note "controller member added" -ResponseFile "responses/06b_add_controller_member.body"

    # 7) Create task
    $taskResult = Invoke-ApiRequest -Step "07_create_task" -Method "Post" -Uri "$api/tasks/" -Headers $authHeaders -Body @{
        title = "Smoke Task $runTag"
        description = "Golden path"
        project_id = $projectId
        assignee_id = $executorId
        controller_id = $controllerId
        due_date = "2030-01-01T10:00:00Z"
        workflow_status_id = $statusNewId
    }
    Assert-200 -Step "07_create_task" -Result $taskResult
    $taskBody = Parse-JsonBody -Body $taskResult.body -Step "07_create_task"
    if (-not $taskBody.id -or -not ($taskBody.PSObject.Properties.Name -contains "computed_deadline_state") -or -not ($taskBody.PSObject.Properties.Name -contains "is_overdue")) {
        Save-FailureArtifact -Step "07_create_task" -BodyFile $taskResult.body_file
        Add-Step -Step "07_create_task" -HttpCode $taskResult.status_code -StepStatus "FAILED" -Note "Missing id/computed_deadline_state/is_overdue" -ResponseFile "responses/07_create_task.body"
        throw "07_create_task missing required fields"
    }
    $taskId = [int]$taskBody.id
    $ids["TASK_ID"] = "$taskId"
    Add-Step -Step "07_create_task" -HttpCode $taskResult.status_code -StepStatus "PASSED" -Note "task_id=$taskId deadline_state=$($taskBody.computed_deadline_state) is_overdue=$($taskBody.is_overdue)" -ResponseFile "responses/07_create_task.body"

    # 8) Patch task
    $patchResult = Invoke-ApiRequest -Step "08_patch_task" -Method "Patch" -Uri "$api/tasks/$taskId" -Headers $authHeaders -Body @{
        due_date = "2030-01-03T12:00:00Z"
        workflow_status_id = $statusInProgressId
        assignee_id = $executorId
    }
    Assert-200 -Step "08_patch_task" -Result $patchResult
    $patchBody = Parse-JsonBody -Body $patchResult.body -Step "08_patch_task"
    if ([int]$patchBody.workflow_status_id -ne $statusInProgressId -or [int]$patchBody.assignee_id -ne $executorId) {
        Save-FailureArtifact -Step "08_patch_task" -BodyFile $patchResult.body_file
        Add-Step -Step "08_patch_task" -HttpCode $patchResult.status_code -StepStatus "FAILED" -Note "Patched fields mismatch" -ResponseFile "responses/08_patch_task.body"
        throw "08_patch_task field mismatch"
    }
    Add-Step -Step "08_patch_task" -HttpCode $patchResult.status_code -StepStatus "PASSED" -Note "due_date=$($patchBody.due_date) status_id=$($patchBody.workflow_status_id) assignee_id=$($patchBody.assignee_id)" -ResponseFile "responses/08_patch_task.body"

    # 9) Add comment
    $commentResult = Invoke-ApiRequest -Step "09_add_comment" -Method "Post" -Uri "$api/task-comments/" -Headers $authHeaders -Body @{
        task_id = $taskId
        comment = "Smoke comment"
    }
    Assert-200 -Step "09_add_comment" -Result $commentResult
    $commentBody = Parse-JsonBody -Body $commentResult.body -Step "09_add_comment"
    if (-not $commentBody.id) {
        Save-FailureArtifact -Step "09_add_comment" -BodyFile $commentResult.body_file
        Add-Step -Step "09_add_comment" -HttpCode $commentResult.status_code -StepStatus "FAILED" -Note "Missing id" -ResponseFile "responses/09_add_comment.body"
        throw "09_add_comment missing id"
    }
    $ids["COMMENT_ID"] = "$($commentBody.id)"
    Add-Step -Step "09_add_comment" -HttpCode $commentResult.status_code -StepStatus "PASSED" -Note "comment_id=$($commentBody.id)" -ResponseFile "responses/09_add_comment.body"

    # 10) Upload attachment
    $attachmentFile = Join-Path $runDir "smoke.txt"
    Set-Content -Path $attachmentFile -Value "smoke attachment $runTag" -NoNewline
    $uploadBodyFile = Join-Path $responsesDir "10_upload_attachment.body"
    $uploadHttp = & curl.exe -sS -o $uploadBodyFile -w "%{http_code}" -X POST "$api/task-attachments/upload?task_id=$taskId" -H "Authorization: Bearer $token" -F "file=@$attachmentFile;type=text/plain"
    if ($LASTEXITCODE -ne 0) {
        Add-Step -Step "10_upload_attachment" -HttpCode "000" -StepStatus "FAILED" -Note "curl exit $LASTEXITCODE" -ResponseFile "responses/10_upload_attachment.body"
        Save-FailureArtifact -Step "10_upload_attachment" -BodyFile $uploadBodyFile
        throw "10_upload_attachment curl failed"
    }

    $uploadHttp = "$uploadHttp".Trim()
    $uploadBodyRaw = if (Test-Path $uploadBodyFile) { Get-Content -Path $uploadBodyFile -Raw } else { "" }
    if ($uploadHttp -ne "200") {
        Add-Step -Step "10_upload_attachment" -HttpCode $uploadHttp -StepStatus "FAILED" -Note "Expected 200; body: $(Get-Excerpt -Text $uploadBodyRaw)" -ResponseFile "responses/10_upload_attachment.body"
        Save-FailureArtifact -Step "10_upload_attachment" -BodyFile $uploadBodyFile
        throw "10_upload_attachment HTTP $uploadHttp"
    }
    $uploadBody = Parse-JsonBody -Body $uploadBodyRaw -Step "10_upload_attachment"
    if (-not $uploadBody.id) {
        Add-Step -Step "10_upload_attachment" -HttpCode $uploadHttp -StepStatus "FAILED" -Note "Missing id" -ResponseFile "responses/10_upload_attachment.body"
        Save-FailureArtifact -Step "10_upload_attachment" -BodyFile $uploadBodyFile
        throw "10_upload_attachment missing id"
    }
    $attachmentId = [int]$uploadBody.id
    $ids["ATTACHMENT_ID"] = "$attachmentId"
    Add-Step -Step "10_upload_attachment" -HttpCode $uploadHttp -StepStatus "PASSED" -Note "attachment_id=$attachmentId" -ResponseFile "responses/10_upload_attachment.body"

    # 11) Close task
    $closeResult = Invoke-ApiRequest -Step "11_close_task" -Method "Post" -Uri "$api/tasks/$taskId/close" -Headers $authHeaders -Body @{
        comment = "Smoke close"
        attachment_ids = @($attachmentId)
    }
    Assert-200 -Step "11_close_task" -Result $closeResult
    $closeBody = Parse-JsonBody -Body $closeResult.body -Step "11_close_task"
    if (-not $closeBody.closed_at) {
        Save-FailureArtifact -Step "11_close_task" -BodyFile $closeResult.body_file
        Add-Step -Step "11_close_task" -HttpCode $closeResult.status_code -StepStatus "FAILED" -Note "closed_at is null" -ResponseFile "responses/11_close_task.body"
        throw "11_close_task closed_at is null"
    }
    Add-Step -Step "11_close_task" -HttpCode $closeResult.status_code -StepStatus "PASSED" -Note "closed_at=$($closeBody.closed_at)" -ResponseFile "responses/11_close_task.body"

    # 12) History
    $historyResult = Invoke-ApiRequest -Step "12_task_history" -Method "Get" -Uri "$api/tasks/$taskId/history" -Headers $authHeaders
    Assert-200 -Step "12_task_history" -Result $historyResult
    $historyBody = Parse-JsonBody -Body $historyResult.body -Step "12_task_history"
    $actions = @($historyBody.data | ForEach-Object { $_.action })
    foreach ($requiredAction in @("created", "updated", "due_date_changed", "status_changed", "comment_added", "attachment_added", "closed")) {
        if (-not ($actions -contains $requiredAction)) {
            Save-FailureArtifact -Step "12_task_history" -BodyFile $historyResult.body_file
            Add-Step -Step "12_task_history" -HttpCode $historyResult.status_code -StepStatus "FAILED" -Note "Missing action '$requiredAction'" -ResponseFile "responses/12_task_history.body"
            throw "12_task_history missing action $requiredAction"
        }
    }
    Add-Step -Step "12_task_history" -HttpCode $historyResult.status_code -StepStatus "PASSED" -Note "history contains required actions" -ResponseFile "responses/12_task_history.body"

    # 13) Dashboard summary
    $dashboardResult = Invoke-ApiRequest -Step "13_dashboard_summary" -Method "Get" -Uri "$api/dashboards/summary" -Headers $authHeaders
    Assert-200 -Step "13_dashboard_summary" -Result $dashboardResult
    $dashboardBody = Parse-JsonBody -Body $dashboardResult.body -Step "13_dashboard_summary"
    foreach ($field in @("total_tasks", "deadline_in_time_count", "deadline_overdue_count", "closed_in_time_count", "closed_overdue_count")) {
        if (-not ($dashboardBody.PSObject.Properties.Name -contains $field)) {
            Save-FailureArtifact -Step "13_dashboard_summary" -BodyFile $dashboardResult.body_file
            Add-Step -Step "13_dashboard_summary" -HttpCode $dashboardResult.status_code -StepStatus "FAILED" -Note "Missing field '$field'" -ResponseFile "responses/13_dashboard_summary.body"
            throw "13_dashboard_summary missing field $field"
        }
    }
    Add-Step -Step "13_dashboard_summary" -HttpCode $dashboardResult.status_code -StepStatus "PASSED" -Note "schema fields present" -ResponseFile "responses/13_dashboard_summary.body"

    # 14) Calendar summary
    $calendarResult = Invoke-ApiRequest -Step "14_calendar_summary" -Method "Get" -Uri "$api/calendar/summary?date_from=2030-01-01&date_to=2030-01-31&project_id=$projectId" -Headers $authHeaders
    Assert-200 -Step "14_calendar_summary" -Result $calendarResult
    $calendarBody = Parse-JsonBody -Body $calendarResult.body -Step "14_calendar_summary"
    if (-not ($calendarBody.PSObject.Properties.Name -contains "data") -or -not ($calendarBody.data -is [System.Collections.IEnumerable])) {
        Save-FailureArtifact -Step "14_calendar_summary" -BodyFile $calendarResult.body_file
        Add-Step -Step "14_calendar_summary" -HttpCode $calendarResult.status_code -StepStatus "FAILED" -Note "Missing data[]" -ResponseFile "responses/14_calendar_summary.body"
        throw "14_calendar_summary missing data[]"
    }
    Add-Step -Step "14_calendar_summary" -HttpCode $calendarResult.status_code -StepStatus "PASSED" -Note "calendar data[] present" -ResponseFile "responses/14_calendar_summary.body"

    # 15a) CSV export
    $csvHeadersFile = Join-Path $responsesDir "15a_export_csv.headers"
    $csvBodyFile = Join-Path $responsesDir "15a_export_csv.body"
    $csvHttp = & curl.exe -sS -D $csvHeadersFile -o $csvBodyFile -w "%{http_code}" "$api/reports/tasks/export.csv?project_id=$projectId" -H "Authorization: Bearer $token"
    if ($LASTEXITCODE -ne 0) {
        Add-Step -Step "15a_export_csv" -HttpCode "000" -StepStatus "FAILED" -Note "curl exit $LASTEXITCODE" -ResponseFile "responses/15a_export_csv.body"
        Save-FailureArtifact -Step "15a_export_csv" -BodyFile $csvBodyFile -HeadersFile $csvHeadersFile
        throw "15a_export_csv curl failed"
    }
    $csvHttp = "$csvHttp".Trim()
    if ($csvHttp -ne "200") {
        $csvRaw = if (Test-Path $csvBodyFile) { Get-Content -Path $csvBodyFile -Raw } else { "" }
        Add-Step -Step "15a_export_csv" -HttpCode $csvHttp -StepStatus "FAILED" -Note "Expected 200; body: $(Get-Excerpt -Text $csvRaw)" -ResponseFile "responses/15a_export_csv.body"
        Save-FailureArtifact -Step "15a_export_csv" -BodyFile $csvBodyFile -HeadersFile $csvHeadersFile
        throw "15a_export_csv HTTP $csvHttp"
    }
    $csvContentType = (Get-Content -Path $csvHeadersFile | Where-Object { $_ -match "^content-type:" } | Select-Object -First 1)
    if (-not $csvContentType -or $csvContentType.ToLower() -notmatch "text/csv") {
        Add-Step -Step "15a_export_csv" -HttpCode $csvHttp -StepStatus "FAILED" -Note "Unexpected content-type: $csvContentType" -ResponseFile "responses/15a_export_csv.body"
        Save-FailureArtifact -Step "15a_export_csv" -BodyFile $csvBodyFile -HeadersFile $csvHeadersFile
        throw "15a_export_csv invalid content-type"
    }
    $csvFirstLine = (Get-Content -Path $csvBodyFile -TotalCount 1)
    Add-Step -Step "15a_export_csv" -HttpCode $csvHttp -StepStatus "PASSED" -Note "content-type=$($csvContentType.Split(':', 2)[1].Trim()); first_line=$(Get-Excerpt -Text $csvFirstLine -MaxLength 140)" -ResponseFile "responses/15a_export_csv.body"

    # 15b) XLSX export
    $xlsxHeadersFile = Join-Path $responsesDir "15b_export_xlsx.headers"
    $xlsxBodyFile = Join-Path $responsesDir "15b_export_xlsx.body"
    $xlsxHttp = & curl.exe -sS -D $xlsxHeadersFile -o $xlsxBodyFile -w "%{http_code}" "$api/reports/tasks/export.xlsx?project_id=$projectId" -H "Authorization: Bearer $token"
    if ($LASTEXITCODE -ne 0) {
        Add-Step -Step "15b_export_xlsx" -HttpCode "000" -StepStatus "FAILED" -Note "curl exit $LASTEXITCODE" -ResponseFile "responses/15b_export_xlsx.body"
        Save-FailureArtifact -Step "15b_export_xlsx" -BodyFile $xlsxBodyFile -HeadersFile $xlsxHeadersFile
        throw "15b_export_xlsx curl failed"
    }
    $xlsxHttp = "$xlsxHttp".Trim()
    if ($xlsxHttp -ne "200") {
        Add-Step -Step "15b_export_xlsx" -HttpCode $xlsxHttp -StepStatus "FAILED" -Note "Expected 200" -ResponseFile "responses/15b_export_xlsx.body"
        Save-FailureArtifact -Step "15b_export_xlsx" -BodyFile $xlsxBodyFile -HeadersFile $xlsxHeadersFile
        throw "15b_export_xlsx HTTP $xlsxHttp"
    }
    $xlsxContentType = (Get-Content -Path $xlsxHeadersFile | Where-Object { $_ -match "^content-type:" } | Select-Object -First 1)
    if (-not $xlsxContentType -or $xlsxContentType.ToLower() -notmatch "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet") {
        Add-Step -Step "15b_export_xlsx" -HttpCode $xlsxHttp -StepStatus "FAILED" -Note "Unexpected content-type: $xlsxContentType" -ResponseFile "responses/15b_export_xlsx.body"
        Save-FailureArtifact -Step "15b_export_xlsx" -BodyFile $xlsxBodyFile -HeadersFile $xlsxHeadersFile
        throw "15b_export_xlsx invalid content-type"
    }
    $magic = [BitConverter]::ToString((Get-Content -Path $xlsxBodyFile -Encoding Byte -TotalCount 8)).Replace("-", "").ToLowerInvariant()
    Add-Step -Step "15b_export_xlsx" -HttpCode $xlsxHttp -StepStatus "PASSED" -Note "content-type=$($xlsxContentType.Split(':', 2)[1].Trim()); magic=$magic" -ResponseFile "responses/15b_export_xlsx.body"

    Write-Log "Smoke scenario passed all steps"
}
catch {
    $status = "FAILED"
    $failReason = $_.Exception.Message
    Write-Log "Smoke failed: $failReason" "ERROR"
}
finally {
    Complete-And-WriteSummary
    if ($status -eq "PASSED") {
        Write-Log "Smoke completed successfully"
        exit 0
    }
    else {
        exit 1
    }
}
