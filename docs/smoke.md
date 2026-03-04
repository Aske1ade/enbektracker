# Golden Smoke Scenario (Backend MVP)

This document fixes a single canonical manual scenario for the task tracker MVP.

## Preconditions

1. Stack is up:
   - `docker compose up -d --build`
2. Backend is healthy:
   - `GET /api/v1/utils/health-check/` -> `true`
3. Use base URL:
   - `http://localhost`
4. Default admin credentials from `.env`:
   - `FIRST_SUPERUSER`
   - `FIRST_SUPERUSER_PASSWORD`

## Variables

```bash
BASE_URL="http://localhost"
API="$BASE_URL/api/v1"
ADMIN_EMAIL="admin@example.com"
ADMIN_PASSWORD="<from .env>"
```

## 1) Login

```bash
curl -s -X POST "$API/auth/access-token" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d "username=$ADMIN_EMAIL&password=$ADMIN_PASSWORD"
```

Expected:
- HTTP `200`
- JSON contains `access_token`

Save token:

```bash
TOKEN="<access_token>"
AUTH_HEADER="Authorization: Bearer $TOKEN"
```

## 2) Create Department

```bash
curl -s -X POST "$API/departments/" \
  -H "$AUTH_HEADER" \
  -H 'Content-Type: application/json' \
  -d '{
    "name":"Engineering Smoke",
    "code":"ENG_SMOKE",
    "description":"Smoke department"
  }'
```

Expected:
- HTTP `200`
- JSON has `id`

Save:
- `DEPARTMENT_ID`

## 3) Create Project (strict close policy)

```bash
curl -s -X POST "$API/projects/" \
  -H "$AUTH_HEADER" \
  -H 'Content-Type: application/json' \
  -d "{\"name\":\"Smoke Project\",\"description\":\"Golden path project\",\"department_id\":$DEPARTMENT_ID,\"require_close_comment\":true,\"require_close_attachment\":true,\"deadline_yellow_days\":3,\"deadline_normal_days\":5}"
```

Expected:
- HTTP `200`
- JSON has `id`

Save:
- `PROJECT_ID`

## 4) Check auto-created project statuses

```bash
curl -s "$API/project-statuses/?project_id=$PROJECT_ID" \
  -H "$AUTH_HEADER"
```

Expected:
- HTTP `200`
- `count >= 4`
- statuses include codes: `new`, `in_progress`, `blocked`, `done`

Save:
- `STATUS_NEW_ID`
- `STATUS_IN_PROGRESS_ID`

## 5) Create users (executor + controller)

Executor:

```bash
curl -s -X POST "$API/users/" \
  -H "$AUTH_HEADER" \
  -H 'Content-Type: application/json' \
  -d '{
    "email":"smoke.executor@example.com",
    "password":"StrongPass123!",
    "is_active":true,
    "is_superuser":false,
    "system_role":"executor"
  }'
```

Controller:

```bash
curl -s -X POST "$API/users/" \
  -H "$AUTH_HEADER" \
  -H 'Content-Type: application/json' \
  -d '{
    "email":"smoke.controller@example.com",
    "password":"StrongPass123!",
    "is_active":true,
    "is_superuser":false,
    "system_role":"controller"
  }'
```

Expected:
- both HTTP `200`
- both have `id`

Save:
- `EXECUTOR_ID`
- `CONTROLLER_ID`

## 6) Add project members

Executor membership:

```bash
curl -s -X POST "$API/projects/$PROJECT_ID/members" \
  -H "$AUTH_HEADER" \
  -H 'Content-Type: application/json' \
  -d "{\"project_id\":$PROJECT_ID,\"user_id\":$EXECUTOR_ID,\"role\":\"executor\",\"is_active\":true}"
```

Controller membership:

```bash
curl -s -X POST "$API/projects/$PROJECT_ID/members" \
  -H "$AUTH_HEADER" \
  -H 'Content-Type: application/json' \
  -d "{\"project_id\":$PROJECT_ID,\"user_id\":$CONTROLLER_ID,\"role\":\"controller\",\"is_active\":true}"
```

Expected:
- both HTTP `200`

## 7) Create task

```bash
curl -s -X POST "$API/tasks/" \
  -H "$AUTH_HEADER" \
  -H 'Content-Type: application/json' \
  -d "{\"title\":\"Smoke Task\",\"description\":\"Golden path\",\"project_id\":$PROJECT_ID,\"assignee_id\":$EXECUTOR_ID,\"controller_id\":$CONTROLLER_ID,\"due_date\":\"2030-01-01T10:00:00Z\",\"workflow_status_id\":$STATUS_NEW_ID}"
```

Expected:
- HTTP `200`
- has `id`, `computed_deadline_state`, `is_overdue`

Save:
- `TASK_ID`

## 8) Update task (due_date/status/assignee)

```bash
curl -s -X PATCH "$API/tasks/$TASK_ID" \
  -H "$AUTH_HEADER" \
  -H 'Content-Type: application/json' \
  -d "{\"due_date\":\"2030-01-03T12:00:00Z\",\"workflow_status_id\":$STATUS_IN_PROGRESS_ID,\"assignee_id\":$EXECUTOR_ID}"
```

Expected:
- HTTP `200`
- changed fields are reflected

## 9) Add comment

```bash
curl -s -X POST "$API/task-comments/" \
  -H "$AUTH_HEADER" \
  -H 'Content-Type: application/json' \
  -d "{\"task_id\":$TASK_ID,\"comment\":\"Smoke comment\"}"
```

Expected:
- HTTP `200`
- JSON has comment `id`

## 10) Upload attachment

```bash
printf 'smoke attachment' > /tmp/smoke.txt
curl -s -X POST "$API/task-attachments/upload?task_id=$TASK_ID" \
  -H "$AUTH_HEADER" \
  -F "file=@/tmp/smoke.txt;type=text/plain"
```

Expected:
- HTTP `200`
- JSON has `id` as `ATTACHMENT_ID`

## 11) Close task with comment + attachment

```bash
curl -s -X POST "$API/tasks/$TASK_ID/close" \
  -H "$AUTH_HEADER" \
  -H 'Content-Type: application/json' \
  -d "{\"comment\":\"Smoke close\",\"attachment_ids\":[$ATTACHMENT_ID]}"
```

Expected:
- HTTP `200`
- `closed_at` is not null

## 12) Verify history

```bash
curl -s "$API/tasks/$TASK_ID/history" -H "$AUTH_HEADER"
```

Expected:
- HTTP `200`
- contains actions: `created`, `updated`, `due_date_changed`, `status_changed`, `assignee_changed` (if changed), `comment_added`, `attachment_added`, `closed`

## 13) Dashboard summary

```bash
curl -s "$API/dashboards/summary" -H "$AUTH_HEADER"
```

Expected:
- HTTP `200`
- schema fields exist: `total_tasks`, `deadline_in_time_count`, `deadline_overdue_count`, `closed_in_time_count`, `closed_overdue_count`

## 14) Calendar summary

```bash
curl -s "$API/calendar/summary?date_from=2030-01-01&date_to=2030-01-31&project_id=$PROJECT_ID" -H "$AUTH_HEADER"
```

Expected:
- HTTP `200`
- has `data[]`

## 15) Reports export

CSV:

```bash
curl -i "$API/reports/tasks/export.csv?project_id=$PROJECT_ID" -H "$AUTH_HEADER"
```

Expected:
- HTTP `200`
- `Content-Type: text/csv`

XLSX:

```bash
curl -i "$API/reports/tasks/export.xlsx?project_id=$PROJECT_ID" -H "$AUTH_HEADER"
```

Expected:
- HTTP `200`
- `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`

## Evidence block template (fill after run)

```text
DEPARTMENT_ID=
PROJECT_ID=
STATUS_NEW_ID=
STATUS_IN_PROGRESS_ID=
EXECUTOR_ID=
CONTROLLER_ID=
TASK_ID=
ATTACHMENT_ID=
```
