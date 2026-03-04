#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"
LOGS_ROOT="$REPO_ROOT/logs"

API="$BASE_URL/api/v1"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
RUN_ID="smoke-$TIMESTAMP"
RUN_DIR="$LOGS_ROOT/$RUN_ID"
FAILURE_DIR="$RUN_DIR/failure"
RESPONSES_DIR="$RUN_DIR/responses"
STEPS_TSV="$RUN_DIR/steps.tsv"
IDS_FILE="$RUN_DIR/ids.env"
LOG_FILE="$RUN_DIR/smoke.log"
SUMMARY_JSON="$RUN_DIR/summary.json"
SUMMARY_MD="$RUN_DIR/summary.md"

STATUS="PASSED"
FAIL_REASON=""
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
LAST_BODY_FILE=""
LAST_HTTP_CODE=""

mkdir -p "$RUN_DIR" "$FAILURE_DIR" "$RESPONSES_DIR"
: > "$STEPS_TSV"
: > "$IDS_FILE"
: > "$LOG_FILE"

log() {
    local level="$1"
    shift
    local msg="$*"
    printf '%s [%s] %s\n' "$(date +%Y-%m-%d\ %H:%M:%S)" "$level" "$msg" | tee -a "$LOG_FILE"
}

sanitize_note() {
    printf '%s' "$1" | tr '\r\n\t' '   '
}

record_step() {
    local step="$1"
    local code="$2"
    local result="$3"
    local note
    note="$(sanitize_note "$4")"
    local response_rel="$5"
    printf '%s\t%s\t%s\t%s\t%s\n' "$step" "$code" "$result" "$note" "$response_rel" >> "$STEPS_TSV"
}

set_id() {
    local key="$1"
    local value="$2"
    grep -v "^${key}=" "$IDS_FILE" > "$IDS_FILE.tmp" || true
    printf '%s=%s\n' "$key" "$value" >> "$IDS_FILE.tmp"
    mv "$IDS_FILE.tmp" "$IDS_FILE"
}

dotenv_value() {
    local key="$1"
    if [[ ! -f "$ENV_FILE" ]]; then
        return 0
    fi

    local line
    line="$(grep -E "^${key}=" "$ENV_FILE" | head -n 1 || true)"
    if [[ -z "$line" ]]; then
        return 0
    fi

    local value="${line#*=}"
    value="${value%\"}"
    value="${value#\"}"
    value="${value%\'}"
    value="${value#\'}"
    printf '%s' "$value"
}

json_get() {
    local file="$1"
    local path="$2"
    python3 - "$file" "$path" <<'PY'
import json
import sys

file_path = sys.argv[1]
path = sys.argv[2]
with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)

parts = [p for p in path.split(".") if p]
cur = data
for part in parts:
    if isinstance(cur, list):
        idx = int(part)
        cur = cur[idx]
    else:
        cur = cur[part]

if isinstance(cur, bool):
    print("true" if cur else "false")
elif cur is None:
    print("")
else:
    print(cur)
PY
}

make_excerpt() {
    local file="$1"
    python3 - "$file" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
if not path.exists():
    print("")
    raise SystemExit(0)

try:
    text = path.read_text(encoding="utf-8", errors="replace")
except Exception:
    data = path.read_bytes()[:80]
    print(data.hex())
    raise SystemExit(0)

text = " ".join(text.split())
print(text[:220])
PY
}

run_curl() {
    local step="$1"
    shift
    local outfile="$RESPONSES_DIR/${step}.body"

    set +e
    LAST_HTTP_CODE="$(curl -sS -o "$outfile" -w "%{http_code}" "$@" 2>>"$LOG_FILE")"
    local curl_exit=$?
    set -e

    LAST_BODY_FILE="$outfile"

    if [[ $curl_exit -ne 0 ]]; then
        STATUS="FAILED"
        FAIL_REASON="curl failed on ${step}"
        cp "$outfile" "$FAILURE_DIR/${step}.body" 2>/dev/null || true
        record_step "$step" "000" "FAILED" "curl exit ${curl_exit}" "responses/${step}.body"
        log "ERROR" "$FAIL_REASON"
        exit 1
    fi
}

assert_http_200() {
    local step="$1"
    if [[ "$LAST_HTTP_CODE" != "200" ]]; then
        STATUS="FAILED"
        FAIL_REASON="${step} returned HTTP ${LAST_HTTP_CODE}, expected 200"
        cp "$LAST_BODY_FILE" "$FAILURE_DIR/${step}.body" 2>/dev/null || true
        local excerpt
        excerpt="$(make_excerpt "$LAST_BODY_FILE")"
        record_step "$step" "$LAST_HTTP_CODE" "FAILED" "$FAIL_REASON; body: ${excerpt}" "responses/${step}.body"
        log "ERROR" "$FAIL_REASON"
        exit 1
    fi
}

finalize() {
    local exit_code=$?
    local finished_at
    finished_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    if [[ $exit_code -ne 0 && "$STATUS" == "PASSED" ]]; then
        STATUS="FAILED"
        if [[ -z "$FAIL_REASON" ]]; then
            FAIL_REASON="Script exited with code $exit_code"
        fi
    fi

    if [[ -z "$(find "$FAILURE_DIR" -maxdepth 1 -type f -print -quit)" ]]; then
        printf 'No failures captured for run %s\n' "$RUN_ID" > "$FAILURE_DIR/no-failures.txt"
    fi

    python3 - "$STEPS_TSV" "$IDS_FILE" "$SUMMARY_JSON" "$SUMMARY_MD" "$RUN_ID" "$STATUS" "$STARTED_AT" "$finished_at" "$BASE_URL" "$RUN_DIR" "$LOG_FILE" "$FAIL_REASON" <<'PY'
import csv
import json
import pathlib
import sys

(
    steps_tsv,
    ids_file,
    summary_json,
    summary_md,
    run_id,
    status,
    started_at,
    finished_at,
    base_url,
    run_dir,
    log_file,
    fail_reason,
) = sys.argv[1:]

steps = []
steps_path = pathlib.Path(steps_tsv)
if steps_path.exists():
    with steps_path.open("r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            if not row:
                continue
            while len(row) < 5:
                row.append("")
            steps.append(
                {
                    "step": row[0],
                    "http_code": row[1],
                    "status": row[2],
                    "note": row[3],
                    "response_file": row[4],
                }
            )

ids = {}
ids_path = pathlib.Path(ids_file)
if ids_path.exists():
    for raw in ids_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        ids[key.strip()] = value.strip()

payload = {
    "run_id": run_id,
    "status": status,
    "started_at": started_at,
    "finished_at": finished_at,
    "base_url": base_url,
    "artifacts_dir": str(pathlib.Path(run_dir).resolve()),
    "log_file": str(pathlib.Path(log_file).resolve()),
    "summary_json": str(pathlib.Path(summary_json).resolve()),
    "summary_md": str(pathlib.Path(summary_md).resolve()),
    "failure_dir": str((pathlib.Path(run_dir) / "failure").resolve()),
    "fail_reason": fail_reason or None,
    "steps": steps,
    "ids": ids,
}

pathlib.Path(summary_json).write_text(
    json.dumps(payload, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

lines = [
    "# Smoke Summary",
    "",
    f"- Run ID: {run_id}",
    f"- Status: **{status}**",
    f"- Started: {started_at}",
    f"- Finished: {finished_at}",
    f"- Base URL: {base_url}",
    f"- Artifacts dir: {pathlib.Path(run_dir).resolve()}",
    f"- Log file: {pathlib.Path(log_file).resolve()}",
]
if fail_reason:
    lines.append(f"- Fail reason: {fail_reason}")

lines.extend([
    "",
    "| Step | HTTP | Status | Note | Response |",
    "|---|---:|---|---|---|",
])
for item in steps:
    lines.append(
        f"| {item['step']} | {item['http_code']} | {item['status']} | {item['note']} | {item['response_file']} |"
    )

if ids:
    lines.extend(["", "## IDs", ""])
    for key in sorted(ids):
        lines.append(f"- {key}: {ids[key]}")

pathlib.Path(summary_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

    if [[ "$STATUS" == "PASSED" ]]; then
        log "INFO" "Smoke completed successfully"
    else
        log "ERROR" "Smoke failed: $FAIL_REASON"
    fi
}

trap finalize EXIT

ADMIN_EMAIL="${ADMIN_EMAIL:-$(dotenv_value FIRST_SUPERUSER)}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-$(dotenv_value FIRST_SUPERUSER_PASSWORD)}"

if [[ -z "$ADMIN_EMAIL" || -z "$ADMIN_PASSWORD" ]]; then
    STATUS="FAILED"
    FAIL_REASON="Missing admin credentials (ADMIN_EMAIL/ADMIN_PASSWORD or FIRST_SUPERUSER/FIRST_SUPERUSER_PASSWORD in .env)"
    log "ERROR" "$FAIL_REASON"
    exit 1
fi

RUN_TAG="$(date +%Y%m%d%H%M%S)$RANDOM"
DEPARTMENT_CODE="ENGSMK${RUN_TAG: -6}"
EXECUTOR_EMAIL="smoke.executor.${RUN_TAG}@example.com"
CONTROLLER_EMAIL="smoke.controller.${RUN_TAG}@example.com"
COMMON_PASSWORD="StrongPass123!"

log "INFO" "Run ID: $RUN_ID"
log "INFO" "Base URL: $BASE_URL"

# Step 1: Login
run_curl "01_login" \
    -X POST "$API/auth/access-token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    --data-urlencode "username=$ADMIN_EMAIL" \
    --data-urlencode "password=$ADMIN_PASSWORD"
assert_http_200 "01_login"
TOKEN="$(json_get "$LAST_BODY_FILE" "access_token" 2>/dev/null || true)"
if [[ -z "$TOKEN" ]]; then
    STATUS="FAILED"
    FAIL_REASON="01_login succeeded but access_token is missing"
    cp "$LAST_BODY_FILE" "$FAILURE_DIR/01_login.body"
    record_step "01_login" "$LAST_HTTP_CODE" "FAILED" "$FAIL_REASON" "responses/01_login.body"
    log "ERROR" "$FAIL_REASON"
    exit 1
fi
record_step "01_login" "$LAST_HTTP_CODE" "PASSED" "access_token received" "responses/01_login.body"

AUTH_HEADER="Authorization: Bearer $TOKEN"

# Step 2: Create Department
DEP_PAYLOAD=$(cat <<JSON
{"name":"Engineering Smoke $RUN_TAG","code":"$DEPARTMENT_CODE","description":"Smoke department $RUN_TAG"}
JSON
)
run_curl "02_create_department" \
    -X POST "$API/departments/" \
    -H "$AUTH_HEADER" \
    -H "Content-Type: application/json" \
    -d "$DEP_PAYLOAD"
assert_http_200 "02_create_department"
DEPARTMENT_ID="$(json_get "$LAST_BODY_FILE" "id" 2>/dev/null || true)"
if [[ -z "$DEPARTMENT_ID" ]]; then
    STATUS="FAILED"
    FAIL_REASON="02_create_department missing id"
    cp "$LAST_BODY_FILE" "$FAILURE_DIR/02_create_department.body"
    record_step "02_create_department" "$LAST_HTTP_CODE" "FAILED" "$FAIL_REASON" "responses/02_create_department.body"
    log "ERROR" "$FAIL_REASON"
    exit 1
fi
set_id "DEPARTMENT_ID" "$DEPARTMENT_ID"
record_step "02_create_department" "$LAST_HTTP_CODE" "PASSED" "department_id=$DEPARTMENT_ID" "responses/02_create_department.body"

# Step 3: Create Project
PROJECT_PAYLOAD=$(cat <<JSON
{"name":"Smoke Project $RUN_TAG","description":"Golden path project","department_id":$DEPARTMENT_ID,"require_close_comment":true,"require_close_attachment":true,"deadline_yellow_days":3,"deadline_normal_days":5}
JSON
)
run_curl "03_create_project" \
    -X POST "$API/projects/" \
    -H "$AUTH_HEADER" \
    -H "Content-Type: application/json" \
    -d "$PROJECT_PAYLOAD"
assert_http_200 "03_create_project"
PROJECT_ID="$(json_get "$LAST_BODY_FILE" "id" 2>/dev/null || true)"
if [[ -z "$PROJECT_ID" ]]; then
    STATUS="FAILED"
    FAIL_REASON="03_create_project missing id"
    cp "$LAST_BODY_FILE" "$FAILURE_DIR/03_create_project.body"
    record_step "03_create_project" "$LAST_HTTP_CODE" "FAILED" "$FAIL_REASON" "responses/03_create_project.body"
    log "ERROR" "$FAIL_REASON"
    exit 1
fi
set_id "PROJECT_ID" "$PROJECT_ID"
record_step "03_create_project" "$LAST_HTTP_CODE" "PASSED" "project_id=$PROJECT_ID" "responses/03_create_project.body"

# Step 4: Project statuses
run_curl "04_project_statuses" \
    "$API/project-statuses/?project_id=$PROJECT_ID" \
    -H "$AUTH_HEADER"
assert_http_200 "04_project_statuses"
if ! python3 - "$LAST_BODY_FILE" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as f:
    payload = json.load(f)

data = payload.get("data", [])
if len(data) < 4:
    raise SystemExit(1)

codes = {item.get("code") for item in data}
required = {"new", "in_progress", "blocked", "done"}
if not required.issubset(codes):
    raise SystemExit(2)
PY
then
    STATUS="FAILED"
    FAIL_REASON="04_project_statuses validation failed"
    cp "$LAST_BODY_FILE" "$FAILURE_DIR/04_project_statuses.body"
    record_step "04_project_statuses" "$LAST_HTTP_CODE" "FAILED" "$FAIL_REASON" "responses/04_project_statuses.body"
    log "ERROR" "$FAIL_REASON"
    exit 1
fi
STATUS_NEW_ID="$(python3 - "$LAST_BODY_FILE" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as f:
    payload = json.load(f)

statuses = payload.get("data", [])
print(next(item["id"] for item in statuses if item.get("code") == "new"))
PY
)"
STATUS_IN_PROGRESS_ID="$(python3 - "$LAST_BODY_FILE" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as f:
    payload = json.load(f)

statuses = payload.get("data", [])
print(next(item["id"] for item in statuses if item.get("code") == "in_progress"))
PY
)"
set_id "STATUS_NEW_ID" "$STATUS_NEW_ID"
set_id "STATUS_IN_PROGRESS_ID" "$STATUS_IN_PROGRESS_ID"
record_step "04_project_statuses" "$LAST_HTTP_CODE" "PASSED" "statuses ok; new=$STATUS_NEW_ID in_progress=$STATUS_IN_PROGRESS_ID" "responses/04_project_statuses.body"

# Step 5a: Create executor
EXECUTOR_PAYLOAD=$(cat <<JSON
{"email":"$EXECUTOR_EMAIL","password":"$COMMON_PASSWORD","is_active":true,"is_superuser":false,"system_role":"executor"}
JSON
)
run_curl "05a_create_executor" \
    -X POST "$API/users/" \
    -H "$AUTH_HEADER" \
    -H "Content-Type: application/json" \
    -d "$EXECUTOR_PAYLOAD"
assert_http_200 "05a_create_executor"
EXECUTOR_ID="$(json_get "$LAST_BODY_FILE" "id" 2>/dev/null || true)"
if [[ -z "$EXECUTOR_ID" ]]; then
    STATUS="FAILED"
    FAIL_REASON="05a_create_executor missing id"
    cp "$LAST_BODY_FILE" "$FAILURE_DIR/05a_create_executor.body"
    record_step "05a_create_executor" "$LAST_HTTP_CODE" "FAILED" "$FAIL_REASON" "responses/05a_create_executor.body"
    log "ERROR" "$FAIL_REASON"
    exit 1
fi
set_id "EXECUTOR_ID" "$EXECUTOR_ID"
record_step "05a_create_executor" "$LAST_HTTP_CODE" "PASSED" "executor_id=$EXECUTOR_ID" "responses/05a_create_executor.body"

# Step 5b: Create controller
CONTROLLER_PAYLOAD=$(cat <<JSON
{"email":"$CONTROLLER_EMAIL","password":"$COMMON_PASSWORD","is_active":true,"is_superuser":false,"system_role":"controller"}
JSON
)
run_curl "05b_create_controller" \
    -X POST "$API/users/" \
    -H "$AUTH_HEADER" \
    -H "Content-Type: application/json" \
    -d "$CONTROLLER_PAYLOAD"
assert_http_200 "05b_create_controller"
CONTROLLER_ID="$(json_get "$LAST_BODY_FILE" "id" 2>/dev/null || true)"
if [[ -z "$CONTROLLER_ID" ]]; then
    STATUS="FAILED"
    FAIL_REASON="05b_create_controller missing id"
    cp "$LAST_BODY_FILE" "$FAILURE_DIR/05b_create_controller.body"
    record_step "05b_create_controller" "$LAST_HTTP_CODE" "FAILED" "$FAIL_REASON" "responses/05b_create_controller.body"
    log "ERROR" "$FAIL_REASON"
    exit 1
fi
set_id "CONTROLLER_ID" "$CONTROLLER_ID"
record_step "05b_create_controller" "$LAST_HTTP_CODE" "PASSED" "controller_id=$CONTROLLER_ID" "responses/05b_create_controller.body"

# Step 6a: Add executor member
MEMBER_EXEC_PAYLOAD=$(cat <<JSON
{"project_id":$PROJECT_ID,"user_id":$EXECUTOR_ID,"role":"executor","is_active":true}
JSON
)
run_curl "06a_add_executor_member" \
    -X POST "$API/projects/$PROJECT_ID/members" \
    -H "$AUTH_HEADER" \
    -H "Content-Type: application/json" \
    -d "$MEMBER_EXEC_PAYLOAD"
assert_http_200 "06a_add_executor_member"
record_step "06a_add_executor_member" "$LAST_HTTP_CODE" "PASSED" "executor member added" "responses/06a_add_executor_member.body"

# Step 6b: Add controller member
MEMBER_CTRL_PAYLOAD=$(cat <<JSON
{"project_id":$PROJECT_ID,"user_id":$CONTROLLER_ID,"role":"controller","is_active":true}
JSON
)
run_curl "06b_add_controller_member" \
    -X POST "$API/projects/$PROJECT_ID/members" \
    -H "$AUTH_HEADER" \
    -H "Content-Type: application/json" \
    -d "$MEMBER_CTRL_PAYLOAD"
assert_http_200 "06b_add_controller_member"
record_step "06b_add_controller_member" "$LAST_HTTP_CODE" "PASSED" "controller member added" "responses/06b_add_controller_member.body"

# Step 7: Create task
TASK_PAYLOAD=$(cat <<JSON
{"title":"Smoke Task $RUN_TAG","description":"Golden path","project_id":$PROJECT_ID,"assignee_id":$EXECUTOR_ID,"controller_id":$CONTROLLER_ID,"due_date":"2030-01-01T10:00:00Z","workflow_status_id":$STATUS_NEW_ID}
JSON
)
run_curl "07_create_task" \
    -X POST "$API/tasks/" \
    -H "$AUTH_HEADER" \
    -H "Content-Type: application/json" \
    -d "$TASK_PAYLOAD"
assert_http_200 "07_create_task"
TASK_ID="$(json_get "$LAST_BODY_FILE" "id" 2>/dev/null || true)"
TASK_DEADLINE_STATE="$(json_get "$LAST_BODY_FILE" "computed_deadline_state" 2>/dev/null || true)"
TASK_OVERDUE="$(json_get "$LAST_BODY_FILE" "is_overdue" 2>/dev/null || true)"
if [[ -z "$TASK_ID" || -z "$TASK_DEADLINE_STATE" || -z "$TASK_OVERDUE" ]]; then
    STATUS="FAILED"
    FAIL_REASON="07_create_task missing id/computed_deadline_state/is_overdue"
    cp "$LAST_BODY_FILE" "$FAILURE_DIR/07_create_task.body"
    record_step "07_create_task" "$LAST_HTTP_CODE" "FAILED" "$FAIL_REASON" "responses/07_create_task.body"
    log "ERROR" "$FAIL_REASON"
    exit 1
fi
set_id "TASK_ID" "$TASK_ID"
record_step "07_create_task" "$LAST_HTTP_CODE" "PASSED" "task_id=$TASK_ID deadline_state=$TASK_DEADLINE_STATE is_overdue=$TASK_OVERDUE" "responses/07_create_task.body"

# Step 8: Patch task
PATCH_PAYLOAD=$(cat <<JSON
{"due_date":"2030-01-03T12:00:00Z","workflow_status_id":$STATUS_IN_PROGRESS_ID,"assignee_id":$EXECUTOR_ID}
JSON
)
run_curl "08_patch_task" \
    -X PATCH "$API/tasks/$TASK_ID" \
    -H "$AUTH_HEADER" \
    -H "Content-Type: application/json" \
    -d "$PATCH_PAYLOAD"
assert_http_200 "08_patch_task"
PATCH_DUE_DATE="$(json_get "$LAST_BODY_FILE" "due_date" 2>/dev/null || true)"
PATCH_STATUS_ID="$(json_get "$LAST_BODY_FILE" "workflow_status_id" 2>/dev/null || true)"
PATCH_ASSIGNEE="$(json_get "$LAST_BODY_FILE" "assignee_id" 2>/dev/null || true)"
if [[ "$PATCH_STATUS_ID" != "$STATUS_IN_PROGRESS_ID" || "$PATCH_ASSIGNEE" != "$EXECUTOR_ID" ]]; then
    STATUS="FAILED"
    FAIL_REASON="08_patch_task fields mismatch"
    cp "$LAST_BODY_FILE" "$FAILURE_DIR/08_patch_task.body"
    record_step "08_patch_task" "$LAST_HTTP_CODE" "FAILED" "$FAIL_REASON" "responses/08_patch_task.body"
    log "ERROR" "$FAIL_REASON"
    exit 1
fi
record_step "08_patch_task" "$LAST_HTTP_CODE" "PASSED" "due_date=$PATCH_DUE_DATE status_id=$PATCH_STATUS_ID assignee_id=$PATCH_ASSIGNEE" "responses/08_patch_task.body"

# Step 9: Add comment
COMMENT_PAYLOAD=$(cat <<JSON
{"task_id":$TASK_ID,"comment":"Smoke comment"}
JSON
)
run_curl "09_add_comment" \
    -X POST "$API/task-comments/" \
    -H "$AUTH_HEADER" \
    -H "Content-Type: application/json" \
    -d "$COMMENT_PAYLOAD"
assert_http_200 "09_add_comment"
COMMENT_ID="$(json_get "$LAST_BODY_FILE" "id" 2>/dev/null || true)"
if [[ -z "$COMMENT_ID" ]]; then
    STATUS="FAILED"
    FAIL_REASON="09_add_comment missing id"
    cp "$LAST_BODY_FILE" "$FAILURE_DIR/09_add_comment.body"
    record_step "09_add_comment" "$LAST_HTTP_CODE" "FAILED" "$FAIL_REASON" "responses/09_add_comment.body"
    log "ERROR" "$FAIL_REASON"
    exit 1
fi
set_id "COMMENT_ID" "$COMMENT_ID"
record_step "09_add_comment" "$LAST_HTTP_CODE" "PASSED" "comment_id=$COMMENT_ID" "responses/09_add_comment.body"

# Step 10: Upload attachment
ATTACH_FILE="$RUN_DIR/smoke.txt"
printf 'smoke attachment %s' "$RUN_TAG" > "$ATTACH_FILE"
run_curl "10_upload_attachment" \
    -X POST "$API/task-attachments/upload?task_id=$TASK_ID" \
    -H "$AUTH_HEADER" \
    -F "file=@$ATTACH_FILE;type=text/plain"
assert_http_200 "10_upload_attachment"
ATTACHMENT_ID="$(json_get "$LAST_BODY_FILE" "id" 2>/dev/null || true)"
if [[ -z "$ATTACHMENT_ID" ]]; then
    STATUS="FAILED"
    FAIL_REASON="10_upload_attachment missing id"
    cp "$LAST_BODY_FILE" "$FAILURE_DIR/10_upload_attachment.body"
    record_step "10_upload_attachment" "$LAST_HTTP_CODE" "FAILED" "$FAIL_REASON" "responses/10_upload_attachment.body"
    log "ERROR" "$FAIL_REASON"
    exit 1
fi
set_id "ATTACHMENT_ID" "$ATTACHMENT_ID"
record_step "10_upload_attachment" "$LAST_HTTP_CODE" "PASSED" "attachment_id=$ATTACHMENT_ID" "responses/10_upload_attachment.body"

# Step 11: Close task
CLOSE_PAYLOAD=$(cat <<JSON
{"comment":"Smoke close","attachment_ids":[$ATTACHMENT_ID]}
JSON
)
run_curl "11_close_task" \
    -X POST "$API/tasks/$TASK_ID/close" \
    -H "$AUTH_HEADER" \
    -H "Content-Type: application/json" \
    -d "$CLOSE_PAYLOAD"
assert_http_200 "11_close_task"
CLOSED_AT="$(json_get "$LAST_BODY_FILE" "closed_at" 2>/dev/null || true)"
if [[ -z "$CLOSED_AT" || "$CLOSED_AT" == "null" ]]; then
    STATUS="FAILED"
    FAIL_REASON="11_close_task closed_at is null"
    cp "$LAST_BODY_FILE" "$FAILURE_DIR/11_close_task.body"
    record_step "11_close_task" "$LAST_HTTP_CODE" "FAILED" "$FAIL_REASON" "responses/11_close_task.body"
    log "ERROR" "$FAIL_REASON"
    exit 1
fi
record_step "11_close_task" "$LAST_HTTP_CODE" "PASSED" "closed_at=$CLOSED_AT" "responses/11_close_task.body"

# Step 12: History
run_curl "12_task_history" \
    "$API/tasks/$TASK_ID/history" \
    -H "$AUTH_HEADER"
assert_http_200 "12_task_history"
if ! python3 - "$LAST_BODY_FILE" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as f:
    payload = json.load(f)

actions = {item.get("action") for item in payload.get("data", [])}
required = {
    "created",
    "updated",
    "due_date_changed",
    "status_changed",
    "comment_added",
    "attachment_added",
    "closed",
}
if not required.issubset(actions):
    raise SystemExit(1)
PY
then
    STATUS="FAILED"
    FAIL_REASON="12_task_history missing required actions"
    cp "$LAST_BODY_FILE" "$FAILURE_DIR/12_task_history.body"
    record_step "12_task_history" "$LAST_HTTP_CODE" "FAILED" "$FAIL_REASON" "responses/12_task_history.body"
    log "ERROR" "$FAIL_REASON"
    exit 1
fi
record_step "12_task_history" "$LAST_HTTP_CODE" "PASSED" "history contains required actions" "responses/12_task_history.body"

# Step 13: Dashboard summary
run_curl "13_dashboard_summary" \
    "$API/dashboards/summary" \
    -H "$AUTH_HEADER"
assert_http_200 "13_dashboard_summary"
if ! python3 - "$LAST_BODY_FILE" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as f:
    payload = json.load(f)

required = [
    "total_tasks",
    "deadline_in_time_count",
    "deadline_overdue_count",
    "closed_in_time_count",
    "closed_overdue_count",
]
missing = [key for key in required if key not in payload]
if missing:
    raise SystemExit(1)
PY
then
    STATUS="FAILED"
    FAIL_REASON="13_dashboard_summary missing schema fields"
    cp "$LAST_BODY_FILE" "$FAILURE_DIR/13_dashboard_summary.body"
    record_step "13_dashboard_summary" "$LAST_HTTP_CODE" "FAILED" "$FAIL_REASON" "responses/13_dashboard_summary.body"
    log "ERROR" "$FAIL_REASON"
    exit 1
fi
record_step "13_dashboard_summary" "$LAST_HTTP_CODE" "PASSED" "schema fields present" "responses/13_dashboard_summary.body"

# Step 14: Calendar summary
run_curl "14_calendar_summary" \
    "$API/calendar/summary?date_from=2030-01-01&date_to=2030-01-31&project_id=$PROJECT_ID" \
    -H "$AUTH_HEADER"
assert_http_200 "14_calendar_summary"
if ! python3 - "$LAST_BODY_FILE" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as f:
    payload = json.load(f)

if "data" not in payload or not isinstance(payload["data"], list):
    raise SystemExit(1)
PY
then
    STATUS="FAILED"
    FAIL_REASON="14_calendar_summary missing data[]"
    cp "$LAST_BODY_FILE" "$FAILURE_DIR/14_calendar_summary.body"
    record_step "14_calendar_summary" "$LAST_HTTP_CODE" "FAILED" "$FAIL_REASON" "responses/14_calendar_summary.body"
    log "ERROR" "$FAIL_REASON"
    exit 1
fi
record_step "14_calendar_summary" "$LAST_HTTP_CODE" "PASSED" "calendar data[] present" "responses/14_calendar_summary.body"

# Step 15a: Reports export CSV
CSV_HEADERS="$RESPONSES_DIR/15a_export_csv.headers"
CSV_BODY="$RESPONSES_DIR/15a_export_csv.body"
set +e
CSV_HTTP_CODE="$(curl -sS -D "$CSV_HEADERS" -o "$CSV_BODY" -w "%{http_code}" "$API/reports/tasks/export.csv?project_id=$PROJECT_ID" -H "$AUTH_HEADER" 2>>"$LOG_FILE")"
CSV_EXIT=$?
set -e
if [[ $CSV_EXIT -ne 0 ]]; then
    STATUS="FAILED"
    FAIL_REASON="15a_export_csv curl failed"
    cp "$CSV_BODY" "$FAILURE_DIR/15a_export_csv.body" 2>/dev/null || true
    record_step "15a_export_csv" "000" "FAILED" "$FAIL_REASON" "responses/15a_export_csv.body"
    log "ERROR" "$FAIL_REASON"
    exit 1
fi
if [[ "$CSV_HTTP_CODE" != "200" ]]; then
    STATUS="FAILED"
    FAIL_REASON="15a_export_csv returned HTTP $CSV_HTTP_CODE"
    cp "$CSV_BODY" "$FAILURE_DIR/15a_export_csv.body" 2>/dev/null || true
    record_step "15a_export_csv" "$CSV_HTTP_CODE" "FAILED" "$FAIL_REASON" "responses/15a_export_csv.body"
    log "ERROR" "$FAIL_REASON"
    exit 1
fi
CSV_CONTENT_TYPE="$(grep -i '^content-type:' "$CSV_HEADERS" | head -n 1 | awk -F':' '{print $2}' | tr -d '\r' | xargs)"
if [[ "$CSV_CONTENT_TYPE" != text/csv* ]]; then
    STATUS="FAILED"
    FAIL_REASON="15a_export_csv unexpected content-type: $CSV_CONTENT_TYPE"
    cp "$CSV_HEADERS" "$FAILURE_DIR/15a_export_csv.headers" 2>/dev/null || true
    cp "$CSV_BODY" "$FAILURE_DIR/15a_export_csv.body" 2>/dev/null || true
    record_step "15a_export_csv" "$CSV_HTTP_CODE" "FAILED" "$FAIL_REASON" "responses/15a_export_csv.body"
    log "ERROR" "$FAIL_REASON"
    exit 1
fi
CSV_EXCERPT="$(head -n 1 "$CSV_BODY" | tr '\r\n\t' '   ' | cut -c1-200)"
record_step "15a_export_csv" "$CSV_HTTP_CODE" "PASSED" "content-type=$CSV_CONTENT_TYPE; first_line=$CSV_EXCERPT" "responses/15a_export_csv.body"

# Step 15b: Reports export XLSX
XLSX_HEADERS="$RESPONSES_DIR/15b_export_xlsx.headers"
XLSX_BODY="$RESPONSES_DIR/15b_export_xlsx.body"
set +e
XLSX_HTTP_CODE="$(curl -sS -D "$XLSX_HEADERS" -o "$XLSX_BODY" -w "%{http_code}" "$API/reports/tasks/export.xlsx?project_id=$PROJECT_ID" -H "$AUTH_HEADER" 2>>"$LOG_FILE")"
XLSX_EXIT=$?
set -e
if [[ $XLSX_EXIT -ne 0 ]]; then
    STATUS="FAILED"
    FAIL_REASON="15b_export_xlsx curl failed"
    cp "$XLSX_BODY" "$FAILURE_DIR/15b_export_xlsx.body" 2>/dev/null || true
    record_step "15b_export_xlsx" "000" "FAILED" "$FAIL_REASON" "responses/15b_export_xlsx.body"
    log "ERROR" "$FAIL_REASON"
    exit 1
fi
if [[ "$XLSX_HTTP_CODE" != "200" ]]; then
    STATUS="FAILED"
    FAIL_REASON="15b_export_xlsx returned HTTP $XLSX_HTTP_CODE"
    cp "$XLSX_BODY" "$FAILURE_DIR/15b_export_xlsx.body" 2>/dev/null || true
    record_step "15b_export_xlsx" "$XLSX_HTTP_CODE" "FAILED" "$FAIL_REASON" "responses/15b_export_xlsx.body"
    log "ERROR" "$FAIL_REASON"
    exit 1
fi
XLSX_CONTENT_TYPE="$(grep -i '^content-type:' "$XLSX_HEADERS" | head -n 1 | awk -F':' '{print $2}' | tr -d '\r' | xargs)"
if [[ "$XLSX_CONTENT_TYPE" != application/vnd.openxmlformats-officedocument.spreadsheetml.sheet* ]]; then
    STATUS="FAILED"
    FAIL_REASON="15b_export_xlsx unexpected content-type: $XLSX_CONTENT_TYPE"
    cp "$XLSX_HEADERS" "$FAILURE_DIR/15b_export_xlsx.headers" 2>/dev/null || true
    cp "$XLSX_BODY" "$FAILURE_DIR/15b_export_xlsx.body" 2>/dev/null || true
    record_step "15b_export_xlsx" "$XLSX_HTTP_CODE" "FAILED" "$FAIL_REASON" "responses/15b_export_xlsx.body"
    log "ERROR" "$FAIL_REASON"
    exit 1
fi
XLSX_MAGIC="$(xxd -p -l 8 "$XLSX_BODY" | tr -d '\n')"
record_step "15b_export_xlsx" "$XLSX_HTTP_CODE" "PASSED" "content-type=$XLSX_CONTENT_TYPE; magic=$XLSX_MAGIC" "responses/15b_export_xlsx.body"

log "INFO" "Smoke scenario passed all steps"
