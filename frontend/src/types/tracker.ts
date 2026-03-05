export type TaskDeadlineState = "green" | "yellow" | "red"
export type TaskUrgencyState = "overdue" | "critical" | "normal" | "reserve"
export type TaskSystemStatus = "new" | "in_progress" | "blocked" | "done"

export interface Department {
  id: number
  name: string
  code?: string | null
  description?: string | null
}

export interface TrackerUser {
  id: number
  email: string
  full_name?: string | null
  is_active: boolean
  is_superuser: boolean
  must_change_password?: boolean
  system_role?:
    | "user"
    | "system_admin"
    | "executor"
    | "controller"
    | "manager"
    | "admin"
  primary_group_id?: number | null
  department_id?: number | null
  department_name?: string | null
  created_at?: string
  updated_at?: string
  can_assign_tasks?: boolean
}

export interface Project {
  id: number
  name: string
  icon?: string | null
  description?: string | null
  organization_id?: number | null
  organization_name?: string | null
  department_id?: number | null
  department_name?: string | null
  department_names?: string[]
  block_id?: number | null
  block_name?: string | null
  require_close_comment: boolean
  require_close_attachment: boolean
  deadline_yellow_days: number
  deadline_normal_days: number
  owner_name?: string | null
  members_count?: number | null
  member_user_ids?: number[]
  tasks_count?: number | null
  created_at?: string
  updated_at?: string
}

export interface ProjectStatus {
  id: number
  project_id: number
  name: string
  code?: TaskSystemStatus | null
  color?: string | null
  order: number
  is_default: boolean
  is_final: boolean
}

export interface ProjectMember {
  id: number
  project_id: number
  user_id: number
  user_name?: string | null
  user_email?: string | null
  role: "reader" | "executor" | "controller" | "manager"
  is_active: boolean
}

export interface ProjectAccessUser {
  user_id: number
  user_name?: string | null
  user_email?: string | null
  role_key: "reader" | "contributor" | "project_admin"
  role_title: string
  is_active: boolean
}

export interface ProjectAccessGroup {
  group_id: number
  group_name?: string | null
  organization_id?: number | null
  role_key: "reader" | "contributor" | "project_admin"
  role_title: string
  is_active: boolean
}

export interface ProjectWall {
  project: Project
  calendar: CalendarViewResponse
  participants: Array<{
    user_id?: number | null
    user_name: string
    tasks_count: number
  }>
  groups: Array<{
    group_id: number
    group_name?: string | null
    organization_id?: number | null
    role_key: "reader" | "contributor" | "project_admin"
    role_title: string
  }>
}

export interface ProjectDepartmentLink {
  department_id: number
  department_name?: string | null
}

export interface WorkBlock {
  id: number
  name: string
  code?: string | null
  description?: string | null
  departments_count: number
  projects_count: number
  managers_count: number
  created_at: string
  updated_at: string
}

export interface Organization {
  id: number
  name: string
  code?: string | null
  description?: string | null
  parent_organization_id?: number | null
  groups_count: number
  projects_count: number
  managers_count: number
  created_at: string
  updated_at: string
}

export interface OrganizationGroup {
  id: number
  organization_id?: number | null
  name: string
  code?: string | null
  description?: string | null
  parent_group_id?: number | null
}

export interface OrganizationTreeNode {
  id: number
  name: string
  code?: string | null
  parent_organization_id?: number | null
  children: OrganizationTreeNode[]
}

export interface OrganizationGroupTreeNode {
  id: number
  organization_id: number
  name: string
  code?: string | null
  parent_group_id?: number | null
  children: OrganizationGroupTreeNode[]
}

export interface OrganizationGroupMember {
  user_id: number
  user_name?: string | null
  user_email?: string | null
  role_name: "owner" | "manager" | "member" | string
  is_active: boolean
}

export interface OrganizationMember {
  user_id: number
  user_name?: string | null
  user_email?: string | null
  role_name: "owner" | "manager" | "member" | string
  is_active: boolean
}

export interface BlockDepartmentLink {
  department_id: number
  department_name?: string | null
}

export interface BlockProjectLink {
  project_id: number
  project_name?: string | null
}

export interface BlockManagerLink {
  user_id: number
  user_name?: string | null
  is_active: boolean
}

export interface Task {
  id: number
  title: string
  description: string
  project_id: number
  project_name?: string | null
  assignee_id?: number | null
  assignee_name?: string | null
  assignee_ids?: number[]
  assignee_names?: string[]
  department_name?: string | null
  creator_id: number
  controller_id?: number | null
  controller_name?: string | null
  due_date: string
  workflow_status_id: number
  workflow_status_name?: string | null
  status_name?: string | null
  computed_deadline_state: TaskDeadlineState
  deadline_state?: TaskDeadlineState | null
  computed_urgency_state: TaskUrgencyState
  is_overdue: boolean
  closed_overdue?: boolean
  last_activity_at?: string | null
  last_activity_by?: string | null
  created_at: string
  updated_at: string
  closed_at?: string | null
}

export interface TaskComment {
  id: number
  task_id: number
  author_id: number
  author_name?: string | null
  author_email?: string | null
  comment: string
  created_at: string
  updated_at: string
}

export interface TaskAttachment {
  id: number
  task_id: number
  uploaded_by_id: number
  file_name: string
  object_key: string
  content_type?: string | null
  size_bytes: number
  created_at: string
}

export interface TaskHistory {
  id: number
  task_id: number
  actor_id: number
  actor_name?: string | null
  action: string
  field_name?: string | null
  old_value?: string | null
  new_value?: string | null
  created_at: string
}

export interface DashboardSummary {
  total_tasks: number
  deadline_in_time_count: number
  deadline_overdue_count: number
  closed_in_time_count: number
  closed_overdue_count: number
  scope_mode?: "managed" | "personal"
  can_use_extended_scope?: boolean
  top_executors: Array<{
    user_id: number
    user_name: string
    count: number
  }>
  top_overdue_executors: Array<{
    user_id: number
    user_name: string
    count: number
  }>
}

export interface DashboardDistributions {
  statuses: Array<{
    status_id: number
    status_name: string
    status_code?: string | null
    count: number
  }>
  departments: Array<{
    department_id?: number | null
    department_name: string
    count: number
  }>
  projects: Array<{
    project_id: number
    project_name: string
    count: number
  }>
}

export interface DashboardTrendPoint {
  bucket_start: string
  total_tasks: number
  in_time_tasks: number
  overdue_tasks: number
  closed_tasks: number
  closed_in_time_tasks: number
}

export interface DashboardTrends {
  period: "day" | "week" | "month"
  date_from: string
  date_to: string
  data: DashboardTrendPoint[]
}

export type DesktopEventType =
  | "assign"
  | "due_soon"
  | "overdue"
  | "status_changed"
  | "close_requested"
  | "close_approved"
  | "comment_added"
  | "system"

export interface DesktopEvent {
  id: number
  user_id: number
  task_id?: number | null
  project_id?: number | null
  event_type: DesktopEventType
  title: string
  message: string
  deeplink?: string | null
  payload_json?: string | null
  created_at: string
}

export interface DesktopEventsPoll {
  data: DesktopEvent[]
  next_cursor?: number | null
  has_more: boolean
  server_time: string
}

export interface CalendarDaySummary {
  day: string
  total_count: number
  overdue_count: number
  in_time_count: number
  closed_count: number
  day_state: "red" | "neutral"
  max_deadline_state: TaskDeadlineState
}

export interface CalendarDayTask {
  id: number
  title: string
  project_id: number
  project_name?: string | null
  assignee_id?: number | null
  assignee_name?: string | null
  department_name?: string | null
  controller_id?: number | null
  controller_name?: string | null
  workflow_status_id: number
  status_name?: string | null
  due_date: string
  computed_deadline_state: TaskDeadlineState
  is_overdue: boolean
  closed_overdue: boolean
  closed_at?: string | null
  updated_at: string
}

export interface CalendarDayDrilldown {
  day: string
  data: CalendarDayTask[]
  count: number
}

export type CalendarViewMode = "day" | "week" | "month" | "year"
export type CalendarScope = "project" | "my"

export interface CalendarViewBucket {
  day: string
  total_count: number
  overdue_count: number
  in_time_count: number
  closed_count: number
  tasks: CalendarDayTask[]
}

export interface CalendarViewResponse {
  mode: CalendarViewMode
  scope: CalendarScope
  date_from: string
  date_to: string
  project_id?: number | null
  data: CalendarViewBucket[]
}

export interface ReportTaskRow {
  task_id: number
  title: string
  project_name: string
  assignee_name: string | null
  department_name: string
  status_name: string
  due_date: string
  is_overdue: boolean
  closed_at?: string | null
  closed_overdue: boolean
  days_overdue: number
}

export interface DisciplineRow {
  department_name: string
  project_name: string
  assignee_name: string
  task_title: string
  due_date: string
  closed_at?: string | null
  days_overdue: number
}

export interface DemoDataCredential {
  email: string
  full_name?: string | null
  username?: string | null
  system_role:
    | "user"
    | "system_admin"
    | "executor"
    | "controller"
    | "manager"
    | "admin"
  department_name?: string | null
  organization_names?: string[]
  group_names?: string[]
  group_roles?: string[]
  password: string
}

export interface DemoDataSummary {
  enabled: boolean
  marker: string
  is_locked?: boolean
  users_count: number
  departments_count: number
  projects_count: number
  tasks_count: number
  credentials: DemoDataCredential[]
}

export interface AdminTaskPolicy {
  allow_backdated_creation: boolean
  overdue_desktop_reminders_enabled: boolean
  overdue_desktop_reminder_interval_minutes: number
  allow_task_scoped_controller_assignment: boolean
}

export interface TaskPolicy {
  allow_task_scoped_controller_assignment: boolean
}

export interface AdminDesktopAgent {
  configured: boolean
  source: "uploaded" | "local_path" | "redirect_url" | "none"
  file_name?: string | null
  content_type?: string | null
  size_bytes?: number | null
  uploaded_at?: string | null
}

export interface AdminTaskBulkDeleteResult {
  matched_tasks: number
  deleted_tasks: number
}

export interface AdminTaskBulkSetControllerResult {
  matched_tasks: number
  updated_tasks: number
}

export interface AdminAccessOrganizationMembership {
  organization_id: number
  organization_name?: string | null
  role_name: string
  is_active: boolean
}

export interface AdminAccessGroupMembership {
  group_id: number
  group_name?: string | null
  organization_id?: number | null
  organization_name?: string | null
  role_name: string
  is_active: boolean
  is_primary: boolean
  is_direct_membership: boolean
}

export interface AdminAccessProjectMembership {
  project_id: number
  project_name?: string | null
  organization_id?: number | null
  organization_name?: string | null
  role: string
  is_active: boolean
}

export interface AdminAccessProjectRoleAssignment {
  project_id: number
  project_name?: string | null
  organization_id?: number | null
  organization_name?: string | null
  role_key: string
  role_title?: string | null
  subject_type: "user" | "group"
  subject_user_id?: number | null
  subject_group_id?: number | null
  subject_group_name?: string | null
  is_active: boolean
}

export interface AdminAccessibleProject {
  project_id: number
  project_name: string
  organization_id?: number | null
  organization_name?: string | null
  reasons: string[]
}

export interface AdminUserAccessMap {
  user_id: number
  email: string
  full_name?: string | null
  system_role: string
  is_superuser: boolean
  primary_group_id?: number | null
  primary_group_name?: string | null
  user_group_ids: number[]
  managed_group_ids: number[]
  managed_organization_ids: number[]
  organizations: AdminAccessOrganizationMembership[]
  groups: AdminAccessGroupMembership[]
  project_memberships: AdminAccessProjectMembership[]
  project_role_assignments: AdminAccessProjectRoleAssignment[]
  accessible_projects: AdminAccessibleProject[]
  notes: string[]
}
