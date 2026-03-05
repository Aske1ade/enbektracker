import axios from "axios"
import { resolveApiBase } from "../config/api"
import type {
  BlockDepartmentLink,
  BlockManagerLink,
  BlockProjectLink,
  CalendarDayDrilldown,
  CalendarViewResponse,
  CalendarDaySummary,
  DashboardDistributions,
  DashboardSummary,
  DashboardTrends,
  DemoDataSummary,
  Department,
  DisciplineRow,
  DesktopEventsPoll,
  Project,
  ProjectAccessGroup,
  ProjectAccessUser,
  ProjectDepartmentLink,
  ProjectMember,
  ProjectWall,
  ProjectStatus,
  Organization,
  OrganizationGroup,
  OrganizationGroupMember,
  OrganizationGroupTreeNode,
  OrganizationMember,
  OrganizationTreeNode,
  ReportTaskRow,
  AdminTaskPolicy,
  TaskPolicy,
  AdminTaskBulkDeleteResult,
  AdminTaskBulkSetControllerResult,
  AdminDesktopAgent,
  AdminUserAccessMap,
  Task,
  TaskAttachment,
  TaskComment,
  TaskHistory,
  TrackerUser,
  WorkBlock,
} from "../types/tracker"

const API_BASE = resolveApiBase()

const api = axios.create({
  baseURL: API_BASE,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token")
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export interface Paginated<T> {
  data: T[]
  count: number
  total?: number
  page?: number
  page_size?: number
}

export interface AdminUserCreatePayload {
  email: string
  full_name?: string | null
  password: string
  is_active?: boolean
  is_superuser?: boolean
  must_change_password?: boolean
  system_role?:
    | "user"
    | "system_admin"
    | "executor"
    | "controller"
    | "manager"
    | "admin"
  department_id?: number | null
}

export interface AdminUserUpdatePayload {
  email?: string | null
  full_name?: string | null
  password?: string | null
  is_active?: boolean
  is_superuser?: boolean
  must_change_password?: boolean
  system_role?:
    | "user"
    | "system_admin"
    | "executor"
    | "controller"
    | "manager"
    | "admin"
  department_id?: number | null
}

export interface AdminDesktopEventsTestResult {
  user_id: number
  mode: "single" | "full"
  created_count: number
  event_ids: number[]
}

export const trackerApi = {
  async dashboardSummary(params?: {
    top_limit?: 5 | 10
    scope_mode?: "managed" | "personal"
    project_id?: number
    department_id?: number
  }): Promise<DashboardSummary> {
    const { data } = await api.get<DashboardSummary>("/dashboards/summary", {
      params,
    })
    return data
  },

  async dashboardDistributions(params?: {
    scope_mode?: "managed" | "personal"
    project_id?: number
    department_id?: number
  }): Promise<DashboardDistributions> {
    const { data } = await api.get<DashboardDistributions>(
      "/dashboards/distributions",
      { params },
    )
    return data
  },

  async dashboardTrends(params?: {
    period?: "day" | "week" | "month"
    scope_mode?: "managed" | "personal"
    project_id?: number
    department_id?: number
    date_from?: string
    date_to?: string
  }): Promise<DashboardTrends> {
    const { data } = await api.get<DashboardTrends>("/dashboards/trends", {
      params,
    })
    return data
  },

  async listDepartments(): Promise<Paginated<Department>> {
    const { data } = await api.get<Paginated<Department>>("/departments/")
    return data
  },

  async listProjects(params?: {
    search?: string
    department_id?: number
    page?: number
    page_size?: number
    sort_by?: string
    sort_order?: "asc" | "desc"
  }): Promise<Paginated<Project>> {
    const normalizedParams = params
      ? {
          ...params,
          page_size: params.page_size
            ? Math.min(params.page_size, 500)
            : params.page_size,
        }
      : undefined

    try {
      const { data } = await api.get<Paginated<Project>>("/projects/", {
        params: normalizedParams,
      })
      return data
    } catch (error) {
      if (
        axios.isAxiosError(error) &&
        error.response?.status === 422 &&
        normalizedParams
      ) {
        const fallbackParams = { ...normalizedParams }
        delete fallbackParams.sort_by
        delete fallbackParams.sort_order
        const { data } = await api.get<Paginated<Project>>("/projects/", {
          params: fallbackParams,
        })
        return data
      }
      throw error
    }
  },

  async listUsers(): Promise<Paginated<TrackerUser>> {
    const { data } = await api.get<Paginated<TrackerUser>>("/users/")
    return data
  },

  async getCurrentUser(): Promise<TrackerUser> {
    const { data } = await api.get<TrackerUser>("/users/me")
    return data
  },

  async adminCreateUser(payload: AdminUserCreatePayload): Promise<TrackerUser> {
    const { data } = await api.post<TrackerUser>("/users/", payload)
    return data
  },

  async adminUpdateUser(
    userId: number,
    payload: AdminUserUpdatePayload,
  ): Promise<TrackerUser> {
    const { data } = await api.patch<TrackerUser>(`/users/${userId}`, payload)
    return data
  },

  async adminDeleteUser(userId: number): Promise<void> {
    await api.delete(`/users/${userId}`)
  },

  async getAdminUserAccessMap(userId: number): Promise<AdminUserAccessMap> {
    const { data } = await api.get<AdminUserAccessMap>(
      `/admin/users/${userId}/access-map`,
    )
    return data
  },

  async getDemoDataStatus(): Promise<DemoDataSummary> {
    const { data } = await api.get<DemoDataSummary>("/admin/demo-data")
    return data
  },

  async setDemoDataEnabled(
    enabled: boolean,
    options?: { admin_password?: string },
  ): Promise<DemoDataSummary> {
    const { data } = await api.put<DemoDataSummary>("/admin/demo-data", {
      enabled,
      admin_password: options?.admin_password,
    })
    return data
  },

  async setDemoDataLock(is_locked: boolean): Promise<DemoDataSummary> {
    const { data } = await api.put<DemoDataSummary>("/admin/demo-data/lock", {
      is_locked,
    })
    return data
  },

  async adminSendDesktopEventsTest(
    userId: number,
    mode: "single" | "full" = "full",
  ): Promise<AdminDesktopEventsTestResult> {
    const { data } = await api.post<AdminDesktopEventsTestResult>(
      `/admin/users/${userId}/desktop-events/test`,
      { mode },
    )
    return data
  },

  async getAdminTaskPolicy(): Promise<AdminTaskPolicy> {
    const { data } = await api.get<AdminTaskPolicy>("/admin/task-policy")
    return data
  },

  async getTaskPolicy(): Promise<TaskPolicy> {
    const { data } = await api.get<TaskPolicy>("/task-policy")
    return data
  },

  async updateAdminTaskPolicy(
    payload: AdminTaskPolicy,
  ): Promise<AdminTaskPolicy> {
    const { data } = await api.put<AdminTaskPolicy>(
      "/admin/task-policy",
      payload,
    )
    return data
  },

  async adminBulkDeleteTasks(payload: {
    project_id?: number
    group_id?: number
    organization_id?: number
    include_completed?: boolean
  }): Promise<AdminTaskBulkDeleteResult> {
    const { data } = await api.post<AdminTaskBulkDeleteResult>(
      "/admin/tasks/bulk-delete",
      payload,
    )
    return data
  },

  async adminBulkSetTaskController(payload: {
    controller_id: number
    project_id?: number
    group_id?: number
    organization_id?: number
    include_completed?: boolean
  }): Promise<AdminTaskBulkSetControllerResult> {
    const { data } = await api.post<AdminTaskBulkSetControllerResult>(
      "/admin/tasks/bulk-set-controller",
      payload,
    )
    return data
  },

  async getAdminDesktopAgent(): Promise<AdminDesktopAgent> {
    const { data } = await api.get<AdminDesktopAgent>("/admin/desktop-agent")
    return data
  },

  async uploadAdminDesktopAgent(file: File): Promise<AdminDesktopAgent> {
    const formData = new FormData()
    formData.append("file", file)
    const { data } = await api.post<AdminDesktopAgent>(
      "/admin/desktop-agent/upload",
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      },
    )
    return data
  },

  async clearAdminDesktopAgent(): Promise<AdminDesktopAgent> {
    const { data } = await api.delete<AdminDesktopAgent>("/admin/desktop-agent")
    return data
  },

  async createProject(payload: {
    name: string
    icon?: string | null
    description?: string
    organization_id?: number | null
    department_id?: number | null
  }): Promise<Project> {
    const { data } = await api.post<Project>("/projects/", {
      name: payload.name,
      icon: payload.icon,
      description: payload.description,
      organization_id: payload.organization_id,
      department_id: payload.department_id,
      require_close_comment: true,
      require_close_attachment: false,
      deadline_yellow_days: 3,
      deadline_normal_days: 5,
    })
    return data
  },

  async getProject(projectId: number): Promise<Project> {
    const { data } = await api.get<Project>(`/projects/${projectId}`)
    return data
  },

  async getProjectWall(
    projectId: number,
    params?: { date?: string; mode?: "day" | "week" | "month" },
  ): Promise<ProjectWall> {
    const { data } = await api.get<ProjectWall>(`/projects/${projectId}/wall`, {
      params,
    })
    return data
  },

  async updateProject(
    projectId: number,
    payload: Partial<{
      name: string
      icon: string | null
      description: string | null
      organization_id: number | null
      department_id: number | null
      require_close_comment: boolean
      require_close_attachment: boolean
      deadline_yellow_days: number
      deadline_normal_days: number
      block_id: number | null
    }>,
  ): Promise<Project> {
    const { data } = await api.patch<Project>(`/projects/${projectId}`, payload)
    return data
  },

  async uploadProjectIcon(projectId: number, file: File): Promise<Project> {
    const formData = new FormData()
    formData.append("file", file)
    const { data } = await api.post<Project>(`/projects/${projectId}/icon`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    })
    return data
  },

  async getProjectDepartments(
    projectId: number,
  ): Promise<Paginated<ProjectDepartmentLink>> {
    const { data } = await api.get<Paginated<ProjectDepartmentLink>>(
      `/projects/${projectId}/departments`,
    )
    return data
  },

  async replaceProjectDepartments(
    projectId: number,
    departmentIds: number[],
  ): Promise<Paginated<ProjectDepartmentLink>> {
    const { data } = await api.put<Paginated<ProjectDepartmentLink>>(
      `/projects/${projectId}/departments`,
      { department_ids: departmentIds },
    )
    return data
  },

  async getProjectStatuses(
    projectId?: number,
    options?: { catalog?: boolean },
  ): Promise<Paginated<ProjectStatus>> {
    const params: Record<string, string | number | boolean> = {}
    if (projectId) {
      params.project_id = projectId
    } else if (options?.catalog !== false) {
      params.catalog = true
    }
    const { data } = await api.get<Paginated<ProjectStatus>>(
      "/project-statuses/",
      { params: Object.keys(params).length ? params : undefined },
    )
    return data
  },

  async listProjectMembers(
    projectId: number,
  ): Promise<Paginated<ProjectMember>> {
    const { data } = await api.get<Paginated<ProjectMember>>(
      `/projects/${projectId}/members`,
    )
    return data
  },

  async createProjectMember(
    projectId: number,
    payload: {
      user_id: number
      role: "reader" | "executor" | "controller" | "manager"
      is_active?: boolean
    },
  ): Promise<ProjectMember> {
    const { data } = await api.post<ProjectMember>(`/projects/${projectId}/members`, {
      project_id: projectId,
      user_id: payload.user_id,
      role: payload.role,
      is_active: payload.is_active ?? true,
    })
    return data
  },

  async updateProjectMember(
    projectId: number,
    userId: number,
    payload: {
      role?: "reader" | "executor" | "controller" | "manager"
      is_active?: boolean
    },
  ): Promise<ProjectMember> {
    const { data } = await api.patch<ProjectMember>(
      `/projects/${projectId}/members/${userId}`,
      payload,
    )
    return data
  },

  async deleteProjectMember(projectId: number, userId: number): Promise<void> {
    await api.delete(`/projects/${projectId}/members/${userId}`)
  },

  async getProjectAccessUsers(
    projectId: number,
  ): Promise<Paginated<ProjectAccessUser>> {
    const { data } = await api.get<Paginated<ProjectAccessUser>>(
      `/projects/${projectId}/access/users`,
    )
    return data
  },

  async replaceProjectAccessUsers(
    projectId: number,
    assignments: Array<{
      user_id: number
      role_key: "reader" | "contributor" | "project_admin"
      is_active?: boolean
    }>,
  ): Promise<Paginated<ProjectAccessUser>> {
    const { data } = await api.put<Paginated<ProjectAccessUser>>(
      `/projects/${projectId}/access/users`,
      { assignments },
    )
    return data
  },

  async getProjectAccessGroups(
    projectId: number,
  ): Promise<Paginated<ProjectAccessGroup>> {
    const { data } = await api.get<Paginated<ProjectAccessGroup>>(
      `/projects/${projectId}/access/groups`,
    )
    return data
  },

  async replaceProjectAccessGroups(
    projectId: number,
    assignments: Array<{
      group_id: number
      role_key: "reader" | "contributor" | "project_admin"
      is_active?: boolean
    }>,
  ): Promise<Paginated<ProjectAccessGroup>> {
    const { data } = await api.put<Paginated<ProjectAccessGroup>>(
      `/projects/${projectId}/access/groups`,
      { assignments },
    )
    return data
  },

  async listTasks(params?: {
    search?: string
    project_id?: number
    department_id?: number
    assignee_id?: number
    controller_id?: number
    workflow_status_id?: number
    deadline_state?: "green" | "yellow" | "red"
    include_completed?: boolean
    due_date_from?: string
    due_date_to?: string
    overdue_only?: boolean
    sort_by?: string
    sort_order?: "asc" | "desc"
    page?: number
    page_size?: number
  }): Promise<Paginated<Task>> {
    const { data } = await api.get<Paginated<Task>>("/tasks/", { params })
    return data
  },

  async getTask(taskId: number): Promise<Task> {
    const { data } = await api.get<Task>(`/tasks/${taskId}`)
    return data
  },

  async createTask(payload: {
    title: string
    description: string
    project_id: number
    assignee_id?: number | null
    assignee_ids?: number[]
    controller_id?: number | null
    due_date: string
  }): Promise<Task> {
    const { data } = await api.post<Task>("/tasks/", payload)
    return data
  },

  async updateTask(
    taskId: number,
    payload: Partial<{
      title: string
      description: string
      assignee_id: number | null
      assignee_ids: number[]
      controller_id: number | null
      due_date: string
      workflow_status_id: number
    }>,
  ): Promise<Task> {
    const { data } = await api.patch<Task>(`/tasks/${taskId}`, payload)
    return data
  },

  async closeTask(
    taskId: number,
    payload: { comment?: string; attachment_ids: number[] },
  ): Promise<Task> {
    const { data } = await api.post<Task>(`/tasks/${taskId}/close`, payload)
    return data
  },

  async submitTaskForReview(taskId: number): Promise<Task> {
    const { data } = await api.post<Task>(`/tasks/${taskId}/submit-review`)
    return data
  },

  async completeTask(taskId: number): Promise<Task> {
    const { data } = await api.post<Task>(`/tasks/${taskId}/complete`)
    return data
  },

  async taskHistory(taskId: number): Promise<Paginated<TaskHistory>> {
    const { data } = await api.get<Paginated<TaskHistory>>(
      `/tasks/${taskId}/history`,
    )
    return data
  },

  async listTaskComments(taskId: number): Promise<Paginated<TaskComment>> {
    const { data } = await api.get<Paginated<TaskComment>>("/task-comments/", {
      params: { task_id: taskId },
    })
    return data
  },

  async addTaskComment(taskId: number, comment: string): Promise<TaskComment> {
    const { data } = await api.post<TaskComment>("/task-comments/", {
      task_id: taskId,
      comment,
    })
    return data
  },

  async listTaskAttachments(
    taskId: number,
  ): Promise<Paginated<TaskAttachment>> {
    const { data } = await api.get<Paginated<TaskAttachment>>(
      "/task-attachments/",
      {
        params: { task_id: taskId },
      },
    )
    return data
  },

  async uploadAttachment(taskId: number, file: File): Promise<TaskAttachment> {
    const formData = new FormData()
    formData.append("file", file)
    const { data } = await api.post<TaskAttachment>(
      `/task-attachments/upload?task_id=${taskId}`,
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      },
    )
    return data
  },

  async deleteAttachment(attachmentId: number): Promise<void> {
    await api.delete(`/task-attachments/${attachmentId}`)
  },

  async downloadAttachmentUrl(attachmentId: number): Promise<string> {
    const { data } = await api.get<{ url: string }>(
      `/task-attachments/${attachmentId}/download-url`,
    )
    return data.url
  },

  async downloadAttachment(
    attachmentId: number,
  ): Promise<{ blob: Blob; fileName?: string }> {
    const response = await api.get<Blob>(`/task-attachments/${attachmentId}/download`, {
      responseType: "blob",
    })
    return {
      blob: response.data,
      fileName: parseContentDispositionFilename(
        response.headers["content-disposition"] as string | undefined,
      ),
    }
  },

  async calendarSummary(params?: {
    date_from?: string
    date_to?: string
    project_id?: number
    department_id?: number
  }): Promise<{ data: CalendarDaySummary[] }> {
    const { data } = await api.get<{ data: CalendarDaySummary[] }>(
      "/calendar/summary",
      {
        params,
      },
    )
    return data
  },

  async calendarDay(params: {
    date: string
    project_id?: number
    department_id?: number
  }): Promise<CalendarDayDrilldown> {
    const { data } = await api.get<CalendarDayDrilldown>("/calendar/day", {
      params,
    })
    return data
  },

  async calendarView(params?: {
    date?: string
    mode?: "day" | "week" | "month" | "year"
    scope?: "project" | "my"
    project_id?: number
    department_id?: number
  }): Promise<CalendarViewResponse> {
    const { data } = await api.get<CalendarViewResponse>("/calendar/view", {
      params,
    })
    return data
  },

  async reportTasks(params?: {
    date_from?: string
    date_to?: string
    project_id?: number
    department_id?: number
    assignee_id?: number
    workflow_status_id?: number
    overdue_only?: boolean
  }): Promise<ReportTaskRow[]> {
    const { data } = await api.get<ReportTaskRow[]>("/reports/tasks", {
      params,
    })
    return data
  },

  reportCsvUrl(params?: {
    date_from?: string
    date_to?: string
    project_id?: number
    department_id?: number
    assignee_id?: number
    workflow_status_id?: number
    overdue_only?: boolean
    template?: "full" | "compact"
    columns?: string
  }): string {
    const query = new URLSearchParams()
    if (!params) {
      return `${API_BASE}/reports/tasks/export.csv`
    }
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null) {
        query.set(key, String(value))
      }
    }
    return `${API_BASE}/reports/tasks/export.csv?${query.toString()}`
  },

  reportXlsxUrl(params?: {
    date_from?: string
    date_to?: string
    project_id?: number
    department_id?: number
    assignee_id?: number
    workflow_status_id?: number
    overdue_only?: boolean
    template?: "full" | "compact"
    columns?: string
    column_widths?: string
  }): string {
    const query = new URLSearchParams()
    if (!params) {
      return `${API_BASE}/reports/tasks/export.xlsx`
    }
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null) {
        query.set(key, String(value))
      }
    }
    return `${API_BASE}/reports/tasks/export.xlsx?${query.toString()}`
  },

  async pollDesktopEvents(params?: {
    cursor?: number
    limit?: number
  }): Promise<DesktopEventsPoll> {
    const { data } = await api.get<DesktopEventsPoll>("/desktop-events/poll", {
      params,
    })
    return data
  },

  async reportDiscipline(params?: {
    date_from?: string
    date_to?: string
    project_id?: number
    department_id?: number
    assignee_id?: number
  }): Promise<Paginated<DisciplineRow>> {
    const { data } = await api.get<Paginated<DisciplineRow>>(
      "/reports/discipline",
      { params },
    )
    return data
  },

  reportDisciplineXlsxUrl(params?: {
    date_from?: string
    date_to?: string
    project_id?: number
    department_id?: number
    assignee_id?: number
  }): string {
    const query = new URLSearchParams()
    if (!params) {
      return `${API_BASE}/reports/discipline/export.xlsx`
    }
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null) {
        query.set(key, String(value))
      }
    }
    return `${API_BASE}/reports/discipline/export.xlsx?${query.toString()}`
  },

  reportDisciplineDocxUrl(params?: {
    date_from?: string
    date_to?: string
    project_id?: number
    department_id?: number
    assignee_id?: number
  }): string {
    const query = new URLSearchParams()
    if (!params) {
      return `${API_BASE}/reports/discipline/export.docx`
    }
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null) {
        query.set(key, String(value))
      }
    }
    return `${API_BASE}/reports/discipline/export.docx?${query.toString()}`
  },

  async listBlocks(): Promise<Paginated<WorkBlock>> {
    const { data } = await api.get<Paginated<WorkBlock>>("/blocks/")
    return data
  },

  async listOrganizations(): Promise<Paginated<Organization>> {
    const { data } = await api.get<Paginated<Organization>>("/organizations/")
    return data
  },

  async listOrganizationTree(): Promise<Paginated<OrganizationTreeNode>> {
    const { data } = await api.get<Paginated<OrganizationTreeNode>>(
      "/organizations/tree",
    )
    return data
  },

  async createOrganization(payload: {
    name: string
    code?: string | null
    description?: string | null
    parent_organization_id?: number | null
  }): Promise<Organization> {
    const { data } = await api.post<Organization>("/organizations/", payload)
    return data
  },

  async updateOrganization(
    organizationId: number,
    payload: Partial<{
      name: string
      code: string | null
      description: string | null
      parent_organization_id: number | null
    }>,
  ): Promise<Organization> {
    const { data } = await api.patch<Organization>(
      `/organizations/${organizationId}`,
      payload,
    )
    return data
  },

  async deleteOrganization(organizationId: number): Promise<void> {
    await api.delete(`/organizations/${organizationId}`)
  },

  async getOrganizationGroups(
    organizationId: number,
  ): Promise<Paginated<OrganizationGroup>> {
    const { data } = await api.get<Paginated<OrganizationGroup>>(
      `/organizations/${organizationId}/groups`,
    )
    return data
  },

  async getOrganizationGroupsTree(
    organizationId: number,
  ): Promise<Paginated<OrganizationGroupTreeNode>> {
    const { data } = await api.get<Paginated<OrganizationGroupTreeNode>>(
      `/organizations/${organizationId}/groups/tree`,
    )
    return data
  },

  async createOrganizationGroup(
    organizationId: number,
    payload: {
      name: string
      code?: string | null
      description?: string | null
      parent_group_id?: number | null
    },
  ): Promise<OrganizationGroup> {
    const { data } = await api.post<OrganizationGroup>(
      `/organizations/${organizationId}/groups`,
      payload,
    )
    return data
  },

  async updateOrganizationGroup(
    organizationId: number,
    groupId: number,
    payload: Partial<{
      name: string
      code: string | null
      description: string | null
      parent_group_id: number | null
    }>,
  ): Promise<OrganizationGroup> {
    const { data } = await api.patch<OrganizationGroup>(
      `/organizations/${organizationId}/groups/${groupId}`,
      payload,
    )
    return data
  },

  async deleteOrganizationGroup(
    organizationId: number,
    groupId: number,
  ): Promise<void> {
    await api.delete(`/organizations/${organizationId}/groups/${groupId}`)
  },

  async listOrganizationGroupMembers(
    groupId: number,
  ): Promise<Paginated<OrganizationGroupMember>> {
    const { data } = await api.get<Paginated<OrganizationGroupMember>>(
      `/organizations/groups/${groupId}/members`,
    )
    return data
  },

  async addOrganizationGroupMember(
    groupId: number,
    payload: {
      user_id: number
      role_name?: "owner" | "manager" | "member"
    },
  ): Promise<OrganizationGroupMember> {
    const { data } = await api.post<OrganizationGroupMember>(
      `/organizations/groups/${groupId}/members`,
      payload,
    )
    return data
  },

  async updateOrganizationGroupMember(
    groupId: number,
    userId: number,
    payload: Partial<{
      role_name: "owner" | "manager" | "member"
      is_active: boolean
    }>,
  ): Promise<OrganizationGroupMember> {
    const { data } = await api.patch<OrganizationGroupMember>(
      `/organizations/groups/${groupId}/members/${userId}`,
      payload,
    )
    return data
  },

  async removeOrganizationGroupMember(
    groupId: number,
    userId: number,
  ): Promise<void> {
    await api.delete(`/organizations/groups/${groupId}/members/${userId}`)
  },

  async listOrganizationMembers(
    organizationId: number,
  ): Promise<Paginated<OrganizationMember>> {
    const { data } = await api.get<Paginated<OrganizationMember>>(
      `/organizations/${organizationId}/members`,
    )
    return data
  },

  async addOrganizationMember(
    organizationId: number,
    payload: {
      user_id: number
      role_name?: "owner" | "manager" | "member"
    },
  ): Promise<OrganizationMember> {
    const { data } = await api.post<OrganizationMember>(
      `/organizations/${organizationId}/members`,
      payload,
    )
    return data
  },

  async updateOrganizationMember(
    organizationId: number,
    userId: number,
    payload: Partial<{
      role_name: "owner" | "manager" | "member"
      is_active: boolean
    }>,
  ): Promise<OrganizationMember> {
    const { data } = await api.patch<OrganizationMember>(
      `/organizations/${organizationId}/members/${userId}`,
      payload,
    )
    return data
  },

  async removeOrganizationMember(
    organizationId: number,
    userId: number,
  ): Promise<void> {
    await api.delete(`/organizations/${organizationId}/members/${userId}`)
  },

  async createBlock(payload: {
    name: string
    code?: string | null
    description?: string | null
  }): Promise<WorkBlock> {
    const { data } = await api.post<WorkBlock>("/blocks/", payload)
    return data
  },

  async updateBlock(
    blockId: number,
    payload: Partial<{
      name: string
      code: string | null
      description: string | null
    }>,
  ): Promise<WorkBlock> {
    const { data } = await api.patch<WorkBlock>(`/blocks/${blockId}`, payload)
    return data
  },

  async deleteBlock(blockId: number): Promise<void> {
    await api.delete(`/blocks/${blockId}`)
  },

  async listBlockDepartments(
    blockId: number,
  ): Promise<Paginated<BlockDepartmentLink>> {
    const { data } = await api.get<Paginated<BlockDepartmentLink>>(
      `/blocks/${blockId}/departments`,
    )
    return data
  },

  async addBlockDepartment(
    blockId: number,
    departmentId: number,
  ): Promise<BlockDepartmentLink> {
    const { data } = await api.post<BlockDepartmentLink>(
      `/blocks/${blockId}/departments`,
      { department_id: departmentId },
    )
    return data
  },

  async removeBlockDepartment(
    blockId: number,
    departmentId: number,
  ): Promise<void> {
    await api.delete(`/blocks/${blockId}/departments/${departmentId}`)
  },

  async listBlockProjects(blockId: number): Promise<Paginated<BlockProjectLink>> {
    const { data } = await api.get<Paginated<BlockProjectLink>>(
      `/blocks/${blockId}/projects`,
    )
    return data
  },

  async addBlockProject(
    blockId: number,
    projectId: number,
  ): Promise<BlockProjectLink> {
    const { data } = await api.post<BlockProjectLink>(
      `/blocks/${blockId}/projects`,
      { project_id: projectId },
    )
    return data
  },

  async removeBlockProject(blockId: number, projectId: number): Promise<void> {
    await api.delete(`/blocks/${blockId}/projects/${projectId}`)
  },

  async listBlockManagers(blockId: number): Promise<Paginated<BlockManagerLink>> {
    const { data } = await api.get<Paginated<BlockManagerLink>>(
      `/blocks/${blockId}/managers`,
    )
    return data
  },

  async addBlockManager(
    blockId: number,
    userId: number,
    isActive = true,
  ): Promise<BlockManagerLink> {
    const { data } = await api.post<BlockManagerLink>(
      `/blocks/${blockId}/managers`,
      { user_id: userId, is_active: isActive },
    )
    return data
  },

  async removeBlockManager(blockId: number, userId: number): Promise<void> {
    await api.delete(`/blocks/${blockId}/managers/${userId}`)
  },
}

function parseContentDispositionFilename(
  value?: string,
): string | undefined {
  if (!value) return undefined
  const utf8Match = value.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1])
    } catch {
      return utf8Match[1]
    }
  }
  const fallbackMatch = value.match(/filename=\"?([^\";]+)\"?/i)
  return fallbackMatch?.[1]
}
