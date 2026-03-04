# Smoke Evidence (Golden Path)

- Run ID: smoke-20260224-053514
- Status: **PASSED**
- Started (UTC): 2026-02-24T00:35:14Z
- Finished (UTC): 2026-02-24T00:35:16Z
- Base URL: http://localhost
- Artifacts: `/mnt/e/DeV/Tracker/logs/smoke-20260224-053514`

## Real IDs

- DEPARTMENT_ID: `2`
- PROJECT_ID: `3`
- STATUS_NEW_ID: `11`
- STATUS_REVIEW_ID: `13`
- EXECUTOR_ID: `4`
- CONTROLLER_ID: `5`
- TASK_ID: `3`
- COMMENT_ID: `3`
- ATTACHMENT_ID: `2`

## HTTP Evidence

| Step | HTTP | Response excerpt |
|---|---:|---|
| `01_login` | 200 | `{"access_token":"<masked>","token_type":"bearer"}` |
| `02_create_department` | 200 | `{"name":"Engineering Smoke 2026022405351428235","code":"ENGSMK428235","description":"Smoke department 2026022405351428235","id":2,"created_at":"2026-02-24T00:35:14.771388Z","update` |
| `03_create_project` | 200 | `{"name":"Smoke Project 2026022405351428235","description":"Golden path project","department_id":2,"require_close_comment":true,"require_close_attachment":true,"deadline_yellow_days` |
| `04_project_statuses` | 200 | `{"data":[{"name":"Новая","code":"new","color":"#3182ce","order":0,"is_default":true,"is_final":false,"id":11,"project_id":3},{"name":"В работе","code":"in_progress","color":"#dd6b2` |
| `05a_create_executor` | 200 | `{"email":"smoke.executor.2026022405351428235@example.com","is_active":true,"is_superuser":false,"full_name":null,"system_role":"executor","department_id":null,"id":4}` |
| `05b_create_controller` | 200 | `{"email":"smoke.controller.2026022405351428235@example.com","is_active":true,"is_superuser":false,"full_name":null,"system_role":"controller","department_id":null,"id":5}` |
| `06a_add_executor_member` | 200 | `{"user_id":4,"role":"executor","is_active":true,"id":6,"project_id":3}` |
| `06b_add_controller_member` | 200 | `{"user_id":5,"role":"controller","is_active":true,"id":7,"project_id":3}` |
| `07_create_task` | 200 | `{"title":"Smoke Task 2026022405351428235","description":"Golden path","project_id":3,"assignee_id":4,"controller_id":5,"due_date":"2030-01-01T10:00:00Z","priority":"high","workflow` |
| `08_patch_task` | 200 | `{"title":"Smoke Task 2026022405351428235","description":"Golden path","project_id":3,"assignee_id":4,"controller_id":5,"due_date":"2030-01-03T12:00:00Z","priority":"high","workflow` |
| `09_add_comment` | 200 | `{"id":3,"task_id":3,"author_id":1,"comment":"Smoke comment","created_at":"2026-02-24T00:35:16.177693Z","updated_at":"2026-02-24T00:35:16.177705Z"}` |
| `10_upload_attachment` | 200 | `{"id":2,"task_id":3,"uploaded_by_id":1,"file_name":"smoke.txt","object_key":"tasks/3/40e270d5-ed31-4e64-baff-6a3aba9fab82-smoke.txt","content_type":"text/plain","size_bytes":36,"cr` |
| `11_close_task` | 200 | `{"title":"Smoke Task 2026022405351428235","description":"Golden path","project_id":3,"assignee_id":4,"controller_id":5,"due_date":"2030-01-03T12:00:00Z","priority":"high","workflow` |
| `12_task_history` | 200 | `{"data":[{"id":15,"task_id":3,"actor_id":1,"action":"attachment_added","field_name":null,"old_value":null,"new_value":"smoke.txt","created_at":"2026-02-24T00:37:30.924006Z"},{"id":` |
| `13_dashboard_summary` | 200 | `{"total_tasks":3,"overdue_tasks":0,"critical_tasks":1,"normal_tasks":0,"reserve_tasks":2,"status_metrics":[{"status_id":1,"status_name":"Новая","count":1},{"status_id":2,"status_na` |
| `14_calendar_summary` | 200 | `{"data":[{"day":"2030-01-03","tasks_count":1,"max_deadline_state":"green"}]}` |
| `15a_export_csv` | 200 | `task_id,title,project_name,assignee_name,department_name,status_name,priority,due_date,is_overdue 3,Smoke Task 2026022405351428235,Smoke Project 2026022405351428235,smoke.executor.` |
| `15b_export_xlsx` | 200 | `xlsx magic: 504b030414000000` |

## Evidence Block

DEPARTMENT_ID=2
PROJECT_ID=3
STATUS_NEW_ID=11
STATUS_REVIEW_ID=13
EXECUTOR_ID=4
CONTROLLER_ID=5
TASK_ID=3
ATTACHMENT_ID=2
