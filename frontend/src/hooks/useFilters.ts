import { useMemo, useState } from "react"

export interface TaskFilters {
  search: string
  projectId?: number
  statusId?: number
  overdueOnly: boolean
  sortBy: "due_date" | "created_at" | "updated_at" | "title"
  sortOrder: "asc" | "desc"
}

const defaultFilters: TaskFilters = {
  search: "",
  overdueOnly: false,
  sortBy: "due_date",
  sortOrder: "asc",
}

export const useFilters = () => {
  const [filters, setFilters] = useState<TaskFilters>(defaultFilters)

  const queryParams = useMemo(
    () => ({
      search: filters.search || undefined,
      project_id: filters.projectId,
      workflow_status_id: filters.statusId,
      overdue_only: filters.overdueOnly || undefined,
      sort_by: filters.sortBy,
      sort_order: filters.sortOrder,
    }),
    [filters],
  )

  return {
    filters,
    setFilters,
    queryParams,
    reset: () => setFilters(defaultFilters),
  }
}

export default useFilters
