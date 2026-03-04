# P0 Stability Gate

P0 is closed only if all checks pass 3 times in a row:

1. `.\scripts\dev.ps1 down`
2. `.\scripts\dev.ps1 up`
3. `GET /api/v1/utils/health-check/` returns `200` and `true`
4. `POST /api/v1/auth/access-token` returns `200`
5. Backend logs include startup chain:
   - `Running script /app/prestart.sh`
   - `alembic upgrade ...`
   - `Initial data created`
   - `Application startup complete`

If any cycle fails, P0 stays open. Run targeted recovery and repeat full 3-cycle verification.

## Automated verifier

Run:

```powershell
.\scripts\p0-verify.ps1
```

Gate is closed only when verifier exits with code `0`.
Artifacts are written to `logs/p0-<timestamp>/` (`p0-verify.log`, `summary.json`, `summary.md`, and `failure/cycle-*` logs on failures).

## P4 Scope Lock (pre-approved)

1. `P4.1` Tasks/Projects table foundation:
   - TanStack Table
   - server-side sorting/filtering/pagination
   - sticky header
   - density modes
   - column visibility persistence
   - full-row deadline coloring
2. `P4.2` Task detail enterprise layout:
   - data panel
   - actions panel
   - comments
   - attachments
   - history
3. `P4.3` Dashboards/Reports/Calendar enhancements:
   - charts
   - drill-down
   - preview grid
   - day drawer
