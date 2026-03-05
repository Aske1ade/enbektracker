import {
  Badge,
  Box,
  Button,
  Accordion,
  AccordionButton,
  AccordionIcon,
  AccordionItem,
  AccordionPanel,
  Checkbox,
  Collapse,
  Container,
  Drawer,
  DrawerBody,
  DrawerCloseButton,
  DrawerContent,
  DrawerHeader,
  DrawerOverlay,
  FormControl,
  FormLabel,
  Grid,
  HStack,
  Heading,
  Icon,
  IconButton,
  Input,
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalFooter,
  ModalHeader,
  ModalOverlay,
  Select,
  Switch,
  Table,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tr,
  VStack,
  Spinner,
  Tooltip,
  Popover,
  PopoverBody,
  PopoverContent,
  PopoverHeader,
  PopoverTrigger,
  Wrap,
  WrapItem,
  useDisclosure,
  useColorModeValue,
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Outlet, createFileRoute } from "@tanstack/react-router"
import {
  type ColumnSizingState,
  type SortingState,
  type VisibilityState,
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table"
import { useEffect, useMemo, useState } from "react"
import {
  FiAlertCircle,
  FiCheckCircle,
  FiClock,
  FiFilter,
  FiInfo,
  FiPlus,
  FiX,
} from "react-icons/fi"

import RichTextContent, { htmlToText } from "../../components/Common/RichTextContent"
import RichTextEditor from "../../components/Common/RichTextEditor"
import useCustomToast from "../../hooks/useCustomToast"
import { trackerApi } from "../../services/trackerApi"
import type {
  Project,
  ProjectMember,
  ProjectStatus,
  Task,
  TrackerUser,
} from "../../types/tracker"

export const Route = createFileRoute("/_layout/tasks")({
  component: TasksPage,
})

type TaskFilters = {
  search: string
  projectId?: number
  departmentId?: number
  assigneeId?: number
  statusId?: number
  deadlineState?: "green" | "yellow" | "red"
  overdueOnly: boolean
  includeCompleted: boolean
}

type TaskTableSettings = {
  columnVisibility: VisibilityState
  columnSizing: ColumnSizingState
}

type SmartQueryResult = {
  plainSearch?: string
  projectId?: number
  departmentId?: number
  assigneeId?: number
  statusId?: number
  overdueOnly?: boolean
}

type AssigneeOption = {
  id: number
  label: string
}

const TASK_TABLE_SETTINGS_KEY = "tracker.tasks.table.v5"
const TASK_FILTER_STATE_KEY = "tracker.tasks.filters.v3"

const DEFAULT_FILTERS: TaskFilters = {
  search: "",
  overdueOnly: false,
  includeCompleted: false,
}

const DEFAULT_SETTINGS: TaskTableSettings = {
  columnVisibility: {
    id: false,
    title: true,
    department_name: true,
    project_name: true,
    assignee_name: true,
    status_name: true,
    deadline_state: false,
    due_date: true,
    updated_at: false,
  },
  columnSizing: {},
}

function readStorage<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return fallback
    return { ...fallback, ...JSON.parse(raw) }
  } catch {
    return fallback
  }
}

function AssigneeMultiPicker({
  value,
  onChange,
  options,
  isDisabled = false,
  addButtonLabel = "Добавить исполнителя",
}: {
  value: string[]
  onChange: (next: string[]) => void
  options: AssigneeOption[]
  isDisabled?: boolean
  addButtonLabel?: string
}) {
  const [search, setSearch] = useState("")
  const [isPickerOpen, setIsPickerOpen] = useState(false)

  const selectedIds = useMemo(() => new Set(value), [value])
  const optionsById = useMemo(
    () => new Map(options.map((option) => [String(option.id), option])),
    [options],
  )
  const selectedOptions = useMemo(
    () =>
      value.map((id) => {
        const existing = optionsById.get(id)
        if (existing) return existing
        return {
          id: Number.isFinite(Number(id)) ? Number(id) : 0,
          label: `Пользователь #${id}`,
        }
      }),
    [optionsById, value],
  )

  const filteredOptions = useMemo(() => {
    const q = search.trim().toLowerCase()
    return options.filter((option) => {
      const id = String(option.id)
      if (selectedIds.has(id)) return false
      if (!q) return true
      return option.label.toLowerCase().includes(q)
    })
  }, [options, search, selectedIds])

  const removeAssignee = (id: string) => {
    if (value.length <= 1) {
      return
    }
    onChange(value.filter((item) => item !== id))
  }

  const addAssignee = (id: string) => {
    if (selectedIds.has(id)) return
    onChange([...value, id])
    setSearch("")
  }

  return (
    <Box>
      <Wrap spacing={2}>
        {selectedOptions.length === 0 ? (
          <WrapItem>
            <Text fontSize="sm" color="ui.muted">
              Пока нет исполнителей
            </Text>
          </WrapItem>
        ) : (
          selectedOptions.map((option) => {
            const optionId = String(option.id)
            return (
              <WrapItem key={`assignee-chip-${optionId}`}>
                <HStack
                  borderWidth="1px"
                  borderColor="ui.border"
                  borderRadius="full"
                  px={3}
                  py={1}
                  spacing={1}
                  bg="ui.secondary"
                  role="group"
                  maxW="360px"
                >
                  <Text fontSize="sm" noOfLines={1}>
                    {option.label}
                  </Text>
                  {!isDisabled ? (
                    <IconButton
                      aria-label="Удалить исполнителя"
                      icon={<FiX />}
                      size="xs"
                      variant="ghost"
                      onClick={() => removeAssignee(optionId)}
                      isDisabled={value.length <= 1}
                      opacity={0.8}
                      _groupHover={{ opacity: 1 }}
                    />
                  ) : null}
                </HStack>
              </WrapItem>
            )
          })
        )}
        {!isDisabled ? (
          <WrapItem>
            <IconButton
              aria-label={addButtonLabel}
              icon={<FiPlus />}
              size="xs"
              borderRadius="full"
              variant="subtle"
              onClick={() => setIsPickerOpen((prev) => !prev)}
            />
          </WrapItem>
        ) : null}
      </Wrap>
      {!isDisabled ? (
        <Collapse in={isPickerOpen} animateOpacity>
          <Box
            mt={2}
            borderWidth="1px"
            borderColor="ui.border"
            borderRadius="lg"
            bg="ui.secondary"
            p={3}
            maxW="420px"
          >
            <HStack justify="space-between" mb={2}>
              <Text fontSize="sm" fontWeight="700">
                Добавить исполнителя
              </Text>
              <IconButton
                aria-label="Скрыть список исполнителей"
                icon={<FiX />}
                size="xs"
                variant="ghost"
                onClick={() => {
                  setIsPickerOpen(false)
                  setSearch("")
                }}
              />
            </HStack>
            <Input
              size="sm"
              placeholder="Поиск по ФИО или email"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              mb={2}
            />
            <VStack align="stretch" spacing={1} maxH="220px" overflowY="auto">
              {filteredOptions.length === 0 ? (
                <Text fontSize="sm" color="ui.muted">
                  Подходящих пользователей нет
                </Text>
              ) : (
                filteredOptions.map((option) => (
                  <Button
                    key={`assignee-option-${option.id}`}
                    variant="ghost"
                    justifyContent="flex-start"
                    onClick={() => addAssignee(String(option.id))}
                    whiteSpace="normal"
                    h="auto"
                    py={2}
                  >
                    {option.label}
                  </Button>
                ))
              )}
            </VStack>
          </Box>
        </Collapse>
      ) : null}
    </Box>
  )
}

function TasksPage() {
  const modal = useDisclosure()
  const taskDrawer = useDisclosure()
  const panelBg = useColorModeValue("white", "#162235")
  const panelAltBg = useColorModeValue("white", "#142033")
  const drawerBg = useColorModeValue("white", "#101b2f")
  const drawerHeaderBg = useColorModeValue("white", "#15263f")
  const drawerTextColor = useColorModeValue("ui.text", "ui.light")
  const tableHeaderBg = useColorModeValue("ui.secondary", "#1A2A42")
  const rowBorderColor = useColorModeValue("gray.200", "ui.border")
  const paginationTextColor = useColorModeValue("gray.600", "ui.muted")
  const attachmentCardBg = useColorModeValue("#FAFCFF", "#1B2C46")
  const showToast = useCustomToast()
  const queryClient = useQueryClient()

  const initialSettings = useMemo(
    () => readStorage(TASK_TABLE_SETTINGS_KEY, DEFAULT_SETTINGS),
    [],
  )
  const initialFilters = useMemo(
    () => readStorage(TASK_FILTER_STATE_KEY, DEFAULT_FILTERS),
    [],
  )

  const [filters, setFilters] = useState<TaskFilters>(initialFilters)
  const [sorting, setSorting] = useState<SortingState>([
    { id: "updated_at", desc: true },
  ])
  const [pagination, setPagination] = useState({ pageIndex: 0, pageSize: 20 })
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(
    Boolean(
      initialFilters.projectId ||
        initialFilters.departmentId ||
        initialFilters.assigneeId ||
        initialFilters.statusId ||
        initialFilters.deadlineState ||
        initialFilters.includeCompleted,
    ),
  )
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>(
    initialSettings.columnVisibility,
  )
  const [columnSizing, setColumnSizing] = useState<ColumnSizingState>(
    initialSettings.columnSizing,
  )
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null)
  const [assigneeSearch, setAssigneeSearch] = useState("")

  const { data: projectsData } = useQuery({
    queryKey: ["projects-for-tasks"],
    queryFn: () =>
      trackerApi.listProjects({
        page: 1,
        page_size: 200,
        sort_by: "name",
        sort_order: "asc",
      }),
  })

  const { data: usersData } = useQuery({
    queryKey: ["tracker-users"],
    queryFn: () => trackerApi.listUsers(),
    retry: false,
    refetchInterval: 30_000,
    refetchIntervalInBackground: true,
  })

  const { data: currentUser } = useQuery({
    queryKey: ["currentUser"],
    queryFn: () => trackerApi.getCurrentUser(),
    retry: false,
  })

  const { data: departmentsData } = useQuery({
    queryKey: ["departments-for-tasks"],
    queryFn: () => trackerApi.listDepartments(),
  })

  const { data: filterStatusesData } = useQuery({
    queryKey: ["task-filter-statuses-catalog"],
    queryFn: () => trackerApi.getProjectStatuses(undefined, { catalog: true }),
  })

  const smartQuery = useMemo(
    () =>
      parseSmartQuery(filters.search, {
        projects: projectsData?.data ?? [],
        users: usersData?.data ?? [],
        statuses: filterStatusesData?.data ?? [],
        departments: departmentsData?.data ?? [],
      }),
    [
      filters.search,
      projectsData?.data,
      usersData?.data,
      filterStatusesData?.data,
      departmentsData?.data,
    ],
  )

  const queryParams = useMemo(() => {
    const activeSort = sorting[0]
    const sortBy = mapSortField(activeSort?.id || "updated_at")
    return {
      search: smartQuery.plainSearch || undefined,
      project_id: filters.projectId ?? smartQuery.projectId,
      department_id: filters.departmentId ?? smartQuery.departmentId,
      assignee_id: filters.assigneeId ?? smartQuery.assigneeId,
      workflow_status_id: filters.statusId ?? smartQuery.statusId,
      deadline_state: filters.deadlineState,
      include_completed: filters.includeCompleted,
      overdue_only:
        filters.overdueOnly || smartQuery.overdueOnly ? true : undefined,
      sort_by: sortBy,
      sort_order: (activeSort?.desc ? "desc" : "asc") as "asc" | "desc",
      page: pagination.pageIndex + 1,
      page_size: pagination.pageSize,
    }
  }, [filters, pagination, smartQuery, sorting])

  const { data: tasksData, isLoading } = useQuery({
    queryKey: ["tasks", queryParams],
    queryFn: () => trackerApi.listTasks(queryParams),
    placeholderData: (previousData) => previousData,
  })

  const [form, setForm] = useState({
    title: "",
    description: "",
    project_id: 0,
    assignee_ids: [] as string[],
    controller_id: "",
    due_date: "",
  })
  const [createFiles, setCreateFiles] = useState<File[]>([])

  const { data: selectedTask, isLoading: selectedTaskLoading } = useQuery({
    queryKey: ["task", selectedTaskId],
    queryFn: () => trackerApi.getTask(selectedTaskId as number),
    enabled: selectedTaskId !== null,
  })
  const { data: selectedTaskHistory } = useQuery({
    queryKey: ["task-history", selectedTaskId],
    queryFn: () => trackerApi.taskHistory(selectedTaskId as number),
    enabled: selectedTaskId !== null,
  })
  const { data: selectedTaskComments } = useQuery({
    queryKey: ["task-comments", selectedTaskId],
    queryFn: () => trackerApi.listTaskComments(selectedTaskId as number),
    enabled: selectedTaskId !== null,
  })
  const { data: selectedTaskAttachments } = useQuery({
    queryKey: ["task-attachments", selectedTaskId],
    queryFn: () => trackerApi.listTaskAttachments(selectedTaskId as number),
    enabled: selectedTaskId !== null,
  })
  const [isEditingTask, setIsEditingTask] = useState(false)
  const [drawerComment, setDrawerComment] = useState("")
  const [editFiles, setEditFiles] = useState<File[]>([])
  const [taskEditor, setTaskEditor] = useState({
    title: "",
    description: "",
    due_date: "",
    workflow_status_id: 0,
    assignee_ids: [] as string[],
    controller_id: "",
  })
  const selectedTaskProjectId = selectedTask?.project_id ?? 0
  const { data: selectedTaskStatuses } = useQuery({
    queryKey: ["task-drawer-statuses", selectedTaskProjectId],
    queryFn: () => trackerApi.getProjectStatuses(selectedTaskProjectId),
    enabled: selectedTaskProjectId > 0,
  })
  const { data: selectedTaskProjectMembersData } = useQuery({
    queryKey: ["task-drawer-project-members", selectedTaskProjectId],
    queryFn: () => trackerApi.listProjectMembers(selectedTaskProjectId),
    enabled: selectedTaskProjectId > 0,
  })
  const { data: createProjectMembersData } = useQuery({
    queryKey: ["task-create-project-members", form.project_id],
    queryFn: () => trackerApi.listProjectMembers(Number(form.project_id)),
    enabled: Number(form.project_id) > 0,
  })

  const toMemberOption = (member: ProjectMember) => {
    const fullName = member.user_name?.trim()
    const email = member.user_email?.trim()
    const label = fullName || email || `Пользователь #${member.user_id}`
    return { id: member.user_id, label }
  }

  const memberOptions = useMemo(() => {
    const users = (usersData?.data ?? []).filter((user) => user.is_active)
    const isAdmin =
      currentUser?.is_superuser || currentUser?.system_role === "system_admin"
    const allowedUsers = !currentUser || isAdmin
      ? users
      : users.filter((user) => {
          if (user.id === currentUser.id) return true
          const samePrimaryGroup =
            currentUser.primary_group_id != null &&
            user.primary_group_id != null &&
            currentUser.primary_group_id === user.primary_group_id
          const sameLegacyDepartment =
            currentUser.department_id != null &&
            user.department_id != null &&
            currentUser.department_id === user.department_id
          return samePrimaryGroup || sameLegacyDepartment
        })
    return allowedUsers.map((user) => {
      const displayName = user.full_name?.trim() || user.email || `Пользователь #${user.id}`
      return {
        id: user.id,
        label: displayName,
      }
    })
  }, [currentUser, usersData])

  const filteredAssigneeOptions = useMemo(() => {
    const query = assigneeSearch.trim().toLowerCase()
    const source = usersData?.data ?? []
    if (!query) return source
    return source.filter((user) => {
      const fullName = (user.full_name || "").toLowerCase()
      const email = (user.email || "").toLowerCase()
      return fullName.includes(query) || email.includes(query)
    })
  }, [assigneeSearch, usersData])

  const projectGroups = useMemo(() => {
    const groups = new Map<string, Project[]>()
    for (const project of projectsData?.data ?? []) {
      const groupName =
        project.block_name || project.organization_name || "Без блока"
      const items = groups.get(groupName) ?? []
      items.push(project)
      groups.set(groupName, items)
    }
    return Array.from(groups.entries())
      .sort((a, b) => a[0].localeCompare(b[0], "ru"))
      .map(([groupName, items]) => [
        groupName,
        items.sort((a, b) => a.name.localeCompare(b.name, "ru")),
      ] as const)
  }, [projectsData?.data])

  const isSystemAdmin = Boolean(
    currentUser?.is_superuser || currentUser?.system_role === "system_admin",
  )
  const isRegularUser = Boolean(currentUser) && !isSystemAdmin
  const selectedTaskProjectMembers = useMemo<ProjectMember[]>(
    () => (selectedTaskProjectMembersData?.data ?? []).filter((member) => member.is_active),
    [selectedTaskProjectMembersData?.data],
  )
  const selectedTaskProjectMemberOptions = useMemo(
    () => selectedTaskProjectMembers.map(toMemberOption),
    [selectedTaskProjectMembers],
  )
  const selectedTaskControllerOptions = useMemo(() => {
    const controllerRows = selectedTaskProjectMembers.filter((member) =>
      ["controller", "manager"].includes(String(member.role).toLowerCase()),
    )
    const baseOptions = controllerRows.map(toMemberOption)
    if (
      selectedTask?.controller_id &&
      !baseOptions.some((option) => option.id === selectedTask.controller_id)
    ) {
      const fallback = selectedTaskProjectMemberOptions.find(
        (option) => option.id === selectedTask.controller_id,
      )
      if (fallback) baseOptions.push(fallback)
    }
    return baseOptions
  }, [selectedTask?.controller_id, selectedTaskProjectMemberOptions, selectedTaskProjectMembers])

  const createProjectMembers = useMemo<ProjectMember[]>(
    () => (createProjectMembersData?.data ?? []).filter((member) => member.is_active),
    [createProjectMembersData?.data],
  )
  const createProjectMemberOptions = useMemo(
    () => createProjectMembers.map(toMemberOption),
    [createProjectMembers],
  )
  const createControllerOptions = useMemo(
    () =>
      createProjectMembers
        .filter((member) =>
          ["controller", "manager"].includes(String(member.role).toLowerCase()),
        )
        .map(toMemberOption),
    [createProjectMembers],
  )

  const createMemberOptions = useMemo(() => {
    if (isRegularUser && currentUser?.id) {
      return memberOptions.filter((member) => member.id === currentUser.id)
    }
    if (form.project_id && createProjectMemberOptions.length > 0) {
      return createProjectMemberOptions
    }
    return memberOptions
  }, [
    createProjectMemberOptions,
    currentUser?.id,
    form.project_id,
    isRegularUser,
    memberOptions,
  ])

  const createMutation = useMutation({
    mutationFn: async () => {
      const normalizedAssigneeIds = Array.from(
        new Set(
          form.assignee_ids
            .map((id) => Number(id))
            .filter((id): id is number => Boolean(id) && Number.isFinite(id)),
        ),
      )
      const effectiveAssigneeIds =
        isRegularUser && currentUser?.id
          ? [currentUser.id]
          : normalizedAssigneeIds
      if (effectiveAssigneeIds.length === 0) {
        throw new Error("У задачи должен быть хотя бы один исполнитель")
      }
      const created = await trackerApi.createTask({
        title: form.title,
        description: form.description,
        project_id: Number(form.project_id),
        assignee_id: effectiveAssigneeIds[0] ?? null,
        assignee_ids: effectiveAssigneeIds,
        controller_id:
          isRegularUser || !form.controller_id
            ? null
            : Number(form.controller_id),
        due_date: new Date(form.due_date).toISOString(),
      })

      const failedUploads: string[] = []
      for (const file of createFiles) {
        try {
          await trackerApi.uploadAttachment(created.id, file)
        } catch {
          failedUploads.push(file.name)
        }
      }
      return { created, failedUploads }
    },
    onSuccess: ({ failedUploads }) => {
      if (failedUploads.length) {
        showToast.error(
          "Задача создана частично",
          `Не удалось загрузить файлы: ${failedUploads.join(", ")}`,
        )
      } else {
        showToast.success("Успешно", "Задача создана")
      }
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard-distributions"] })
      modal.onClose()
      setForm({
        title: "",
        description: "",
        project_id: 0,
        assignee_ids: [],
        controller_id: "",
        due_date: "",
      })
      setCreateFiles([])
    },
    onError: (error) => {
      showToast.error("Не удалось создать задачу", error)
    },
  })

  const updateMutation = useMutation({
    mutationFn: async () => {
      if (!selectedTaskId) throw new Error("Task is not selected")
      const normalizedAssigneeIds = Array.from(
        new Set(
          taskEditor.assignee_ids
            .map((id) => Number(id))
            .filter((id): id is number => Boolean(id) && Number.isFinite(id)),
        ),
      )
      if (normalizedAssigneeIds.length === 0) {
        throw new Error("У задачи должен быть хотя бы один исполнитель")
      }
      return trackerApi.updateTask(selectedTaskId, {
        title: taskEditor.title,
        description: taskEditor.description,
        due_date: new Date(taskEditor.due_date).toISOString(),
        workflow_status_id: Number(taskEditor.workflow_status_id),
        assignee_id: normalizedAssigneeIds[0] ?? null,
        assignee_ids: normalizedAssigneeIds,
        controller_id: taskEditor.controller_id
          ? Number(taskEditor.controller_id)
          : null,
      })
    },
    onSuccess: (updated) => {
      showToast.success("Успешно", "Задача обновлена")
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
      queryClient.invalidateQueries({ queryKey: ["task", updated.id] })
      queryClient.invalidateQueries({ queryKey: ["task-history", updated.id] })
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard-distributions"] })
      setIsEditingTask(false)
      setEditFiles([])
    },
    onError: (error) => {
      showToast.error("Не удалось обновить задачу", error)
    },
  })

  const addCommentMutation = useMutation({
    mutationFn: async () => {
      if (!selectedTaskId) throw new Error("Task is not selected")
      return trackerApi.addTaskComment(selectedTaskId, drawerComment.trim())
    },
    onSuccess: () => {
      setDrawerComment("")
      queryClient.invalidateQueries({ queryKey: ["task-comments", selectedTaskId] })
      queryClient.invalidateQueries({ queryKey: ["task-history", selectedTaskId] })
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
      showToast.success("Успешно", "Комментарий добавлен")
    },
    onError: (error) => {
      showToast.error("Не удалось добавить комментарий", error)
    },
  })

  const uploadEditAttachmentsMutation = useMutation({
    mutationFn: async () => {
      if (!selectedTaskId) throw new Error("Task is not selected")
      if (!editFiles.length) return { uploaded: 0, failed: [] as string[] }
      let uploaded = 0
      const failed: string[] = []
      for (const file of editFiles) {
        try {
          await trackerApi.uploadAttachment(selectedTaskId, file)
          uploaded += 1
        } catch {
          failed.push(file.name)
        }
      }
      return { uploaded, failed }
    },
    onSuccess: ({ uploaded, failed }) => {
      if (uploaded > 0) {
        showToast.success("Успешно", `Загружено файлов: ${uploaded}`)
      }
      if (failed.length > 0) {
        showToast.error(
          "Часть файлов не загружена",
          `Не удалось загрузить: ${failed.join(", ")}`,
        )
      }
      setEditFiles([])
      if (selectedTaskId) {
        queryClient.invalidateQueries({
          queryKey: ["task-attachments", selectedTaskId],
        })
        queryClient.invalidateQueries({ queryKey: ["task-history", selectedTaskId] })
      }
    },
    onError: (error) => {
      showToast.error("Не удалось загрузить вложения", error)
    },
  })

  const submitReviewMutation = useMutation({
    mutationFn: async () => {
      if (!selectedTaskId) throw new Error("Task is not selected")
      return trackerApi.submitTaskForReview(selectedTaskId)
    },
    onSuccess: (updated) => {
      showToast.success("Успешно", "Задача отправлена на проверку")
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
      queryClient.invalidateQueries({ queryKey: ["task", updated.id] })
      queryClient.invalidateQueries({ queryKey: ["task-history", updated.id] })
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard-distributions"] })
    },
    onError: (error) => {
      showToast.error("Не удалось отправить задачу на проверку", error)
    },
  })

  const completeTaskMutation = useMutation({
    mutationFn: async () => {
      if (!selectedTaskId) throw new Error("Task is not selected")
      return trackerApi.completeTask(selectedTaskId)
    },
    onSuccess: (updated) => {
      showToast.success("Успешно", "Задача завершена")
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
      queryClient.invalidateQueries({ queryKey: ["task", updated.id] })
      queryClient.invalidateQueries({ queryKey: ["task-history", updated.id] })
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard-distributions"] })
    },
    onError: (error) => {
      showToast.error("Не удалось завершить задачу", error)
    },
  })

  useEffect(() => {
    localStorage.setItem(
      TASK_TABLE_SETTINGS_KEY,
      JSON.stringify({ columnVisibility, columnSizing }),
    )
  }, [columnVisibility, columnSizing])

  const resetTaskEditorFromTask = (task: Task) => {
    const assigneeIds = (
      task.assignee_ids?.length
        ? task.assignee_ids
        : task.assignee_id
          ? [task.assignee_id]
          : []
    ).map(String)
    setTaskEditor({
      title: task.title,
      description: task.description,
      due_date: toDateTimeLocalValue(task.due_date),
      workflow_status_id: task.workflow_status_id,
      assignee_ids: assigneeIds,
      controller_id: task.controller_id ? String(task.controller_id) : "",
    })
  }

  useEffect(() => {
    if (!selectedTask) return
    resetTaskEditorFromTask(selectedTask)
    setIsEditingTask(false)
    setDrawerComment("")
    setEditFiles([])
  }, [selectedTask])

  useEffect(() => {
    localStorage.setItem(TASK_FILTER_STATE_KEY, JSON.stringify(filters))
  }, [filters])

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const rawTaskId = params.get("taskId")
    if (!rawTaskId) return
    const parsed = Number(rawTaskId)
    if (Number.isNaN(parsed) || parsed <= 0) return
    setSelectedTaskId(parsed)
    taskDrawer.onOpen()
  }, [])

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const source = params.get("from")
    const projectId = params.get("projectId")
    const departmentId = params.get("departmentId")
    const assigneeId = params.get("assigneeId")
    const overdueOnly = params.get("overdueOnly")

    const nextProjectId = parsePositiveInt(projectId)
    const nextDepartmentId = parsePositiveInt(departmentId)
    const nextAssigneeId = parsePositiveInt(assigneeId)
    const nextOverdueOnly =
      overdueOnly === "true" || overdueOnly === "1" || overdueOnly === "да"

    const hasIncomingFilters =
      nextProjectId !== undefined ||
      nextDepartmentId !== undefined ||
      nextAssigneeId !== undefined ||
      nextOverdueOnly

    if (!hasIncomingFilters && source !== "dashboard") return

    setFilters({
      ...DEFAULT_FILTERS,
      projectId: nextProjectId,
      departmentId: nextDepartmentId,
      assigneeId: nextAssigneeId,
      overdueOnly: nextOverdueOnly,
    })
    setPagination((prev) => ({ ...prev, pageIndex: 0 }))
    setShowAdvancedFilters(hasIncomingFilters)
  }, [])

  useEffect(() => {
    const url = new URL(window.location.href)
    if (selectedTaskId) {
      url.searchParams.set("taskId", String(selectedTaskId))
    } else {
      url.searchParams.delete("taskId")
    }
    window.history.replaceState({}, "", url)
  }, [selectedTaskId])

  const columnHelper = createColumnHelper<Task>()
  const columns = useMemo(
    () => [
      columnHelper.accessor("id", {
        id: "id",
        header: "ID",
        size: 70,
        minSize: 60,
        enableResizing: true,
        enableSorting: true,
        cell: (info) => info.getValue(),
      }),
      columnHelper.accessor("title", {
        id: "title",
        header: "Наименование задачи",
        size: 360,
        minSize: 240,
        enableResizing: true,
        enableSorting: true,
        cell: (info) => (
          <Text fontWeight="700" fontSize="sm" noOfLines={1}>
            {info.row.original.title}
          </Text>
        ),
      }),
      columnHelper.accessor("department_name", {
        id: "department_name",
        header: "Департамент",
        size: 180,
        minSize: 130,
        enableResizing: true,
        enableSorting: true,
        cell: (info) => info.getValue() || "-",
      }),
      columnHelper.accessor("project_name", {
        id: "project_name",
        header: "Проект",
        size: 200,
        minSize: 140,
        enableResizing: true,
        enableSorting: true,
        cell: (info) => info.getValue() || `#${info.row.original.project_id}`,
      }),
      columnHelper.accessor("assignee_name", {
        id: "assignee_name",
        header: "Исполнитель",
        size: 190,
        minSize: 140,
        enableResizing: true,
        enableSorting: true,
        cell: (info) =>
          info.row.original.assignee_names?.length
            ? info.row.original.assignee_names.join(", ")
            : info.getValue() || "-",
      }),
      columnHelper.accessor("status_name", {
        id: "status_name",
        header: "Состояние задачи",
        size: 155,
        minSize: 125,
        enableResizing: true,
        enableSorting: true,
        cell: (info) => {
          const value =
            info.getValue() || info.row.original.workflow_status_name || "-"
          return <Badge borderRadius="full">{value}</Badge>
        },
      }),
      columnHelper.display({
        id: "deadline_state",
        header: "Состояние по сроку",
        size: 155,
        minSize: 125,
        enableResizing: true,
        enableSorting: true,
        cell: (info) => (
          <Badge
            colorScheme={deadlineBadgeColor(resolveDeadlineState(info.row.original))}
            borderRadius="full"
          >
            {deadlineBadgeLabel(resolveDeadlineState(info.row.original))}
          </Badge>
        ),
      }),
      columnHelper.accessor("due_date", {
        id: "due_date",
        header: "Срок",
        size: 145,
        minSize: 120,
        enableResizing: true,
        enableSorting: true,
        cell: (info) => formatDate(info.getValue()),
      }),
      columnHelper.accessor("updated_at", {
        id: "updated_at",
        header: "Последнее обновление",
        size: 180,
        minSize: 150,
        enableResizing: true,
        enableSorting: true,
        cell: (info) => formatDateTime(info.getValue()),
      }),
    ],
    [columnHelper],
  )

  const table = useReactTable({
    data: tasksData?.data ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualSorting: true,
    manualPagination: true,
    pageCount: Math.max(
      1,
      Math.ceil((tasksData?.total ?? 0) / pagination.pageSize),
    ),
    state: {
      sorting,
      pagination,
      columnVisibility,
      columnSizing,
    },
    onSortingChange: setSorting,
    onPaginationChange: setPagination,
    onColumnVisibilityChange: setColumnVisibility,
    onColumnSizingChange: setColumnSizing,
    columnResizeMode: "onChange",
    enableColumnResizing: true,
  })

  const totalRows = tasksData?.total ?? 0
  const fromRow =
    totalRows === 0 ? 0 : pagination.pageIndex * pagination.pageSize + 1
  const toRow = Math.min(
    totalRows,
    (pagination.pageIndex + 1) * pagination.pageSize,
  )

  const plainDescription = htmlToText(form.description)
  const hasActiveAdvancedFilters = Boolean(
    filters.projectId ||
      filters.departmentId ||
      filters.assigneeId ||
      filters.statusId ||
      filters.deadlineState ||
      filters.includeCompleted,
  )

  const resetTaskFilters = () => {
    setFilters(DEFAULT_FILTERS)
    setPagination((prev) => ({ ...prev, pageIndex: 0 }))
    setShowAdvancedFilters(false)
  }

  const closeTaskDrawer = () => {
    const url = new URL(window.location.href)
    url.searchParams.delete("taskId")
    window.history.replaceState({}, "", url)
    setIsEditingTask(false)
    setDrawerComment("")
    setEditFiles([])
    setSelectedTaskId(null)
    taskDrawer.onClose()
  }
  const closeCreateModal = () => {
    modal.onClose()
    setForm({
      title: "",
      description: "",
      project_id: 0,
      assignee_ids: [],
      controller_id: "",
      due_date: "",
    })
    setCreateFiles([])
  }

  const selectedStatusLabel = (
    selectedTask?.workflow_status_name ||
    selectedTask?.status_name ||
    ""
  ).toLowerCase()
  const selectedTaskIsDone =
    Boolean(selectedTask?.closed_at) || selectedStatusLabel.includes("готов")
  const selectedTaskIsReview = selectedStatusLabel.includes("провер")
  const selectedTaskAssigneeIds = (
    selectedTask?.assignee_ids?.length
      ? selectedTask.assignee_ids
      : selectedTask?.assignee_id
        ? [selectedTask.assignee_id]
        : []
  ).filter((id): id is number => id != null)
  const isTaskParticipant = Boolean(
    selectedTask &&
      currentUser?.id &&
      (selectedTask.creator_id === currentUser.id ||
        selectedTask.controller_id === currentUser.id ||
        selectedTaskAssigneeIds.includes(currentUser.id)),
  )
  const isTaskAssignee = Boolean(
    selectedTask &&
      currentUser?.id &&
      selectedTaskAssigneeIds.includes(currentUser.id),
  )
  const isProjectControllerOrManager = Boolean(
    currentUser?.id &&
      selectedTaskProjectMembers.some(
        (member) =>
          member.user_id === currentUser.id &&
          ["controller", "manager"].includes(String(member.role).toLowerCase()),
      ),
  )
  const hasReviewMaterial =
    (selectedTaskComments?.count ?? 0) > 0 ||
    (selectedTaskAttachments?.count ?? 0) > 0
  const canManageTaskControls = Boolean(
    selectedTask &&
      (isSystemAdmin ||
        selectedTask.controller_id === currentUser?.id ||
        isProjectControllerOrManager),
  )
  const hasElevatedSystemRole = Boolean(
    currentUser?.is_superuser ||
      ["system_admin", "admin", "manager", "controller"].includes(
        String(currentUser?.system_role || "").toLowerCase(),
      ),
  )
  const canSubmitReview = Boolean(
    selectedTask &&
      !selectedTaskIsDone &&
      !selectedTaskIsReview &&
      isTaskAssignee &&
      hasReviewMaterial &&
      !canManageTaskControls &&
      !hasElevatedSystemRole,
  )
  const canCompleteTask = Boolean(
    selectedTask &&
      !selectedTaskIsDone &&
      (canManageTaskControls || hasElevatedSystemRole),
  )
  const canEditTask = Boolean(
    selectedTask && (isTaskParticipant || canManageTaskControls || isSystemAdmin),
  )

  const downloadAttachment = async (
    attachmentId: number,
    fallbackFileName: string,
  ) => {
    try {
      const { blob, fileName } = await trackerApi.downloadAttachment(
        attachmentId,
      )
      const objectUrl = URL.createObjectURL(blob)
      const anchor = document.createElement("a")
      anchor.href = objectUrl
      anchor.download = fileName || fallbackFileName || `attachment-${attachmentId}`
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(objectUrl)
    } catch (error) {
      showToast.error("Не удалось скачать вложение", error)
    }
  }

  return (
    <Container maxW="full" py={6}>
      <HStack justify="space-between" mb={4} align="center" flexWrap="wrap">
        <Box>
          <Heading size="lg">Задачи</Heading>
        </Box>
        <Button variant="primary" onClick={modal.onOpen}>
          Создать задачу
        </Button>
      </HStack>

      <Box
        borderWidth="1px"
        borderColor="ui.border"
        borderRadius="10px"
        p={4}
        mb={4}
        bg={panelBg}
        boxShadow="sm"
      >
        <HStack spacing={3} align="end" flexWrap="wrap">
          <FormControl flex="1" minW="280px">
            <HStack justify="space-between" mb={1}>
              <FormLabel mb={0}>Поиск</FormLabel>
              <Tooltip
                hasArrow
                placement="top"
                label="Умный поиск: project:Название assignee:Имя department:Название status:Название overdue:true"
              >
                <Text fontSize="xs" color="ui.muted" cursor="help">
                  <Icon as={FiInfo} mr={1} />
                  Умный синтаксис
                </Text>
              </Tooltip>
            </HStack>
            <Input
              value={filters.search}
              onChange={(e) => {
                setFilters((prev) => ({ ...prev, search: e.target.value }))
                setPagination((prev) => ({ ...prev, pageIndex: 0 }))
              }}
              placeholder="Поиск по задаче, проекту, исполнителю, департаменту"
            />
          </FormControl>

          <FormControl w={{ base: "100%", md: "170px" }}>
            <FormLabel>Просроченные</FormLabel>
            <Switch
              isChecked={filters.overdueOnly}
              onChange={(e) => {
                setFilters((prev) => ({
                  ...prev,
                  overdueOnly: e.target.checked,
                }))
                setPagination((prev) => ({ ...prev, pageIndex: 0 }))
              }}
            />
          </FormControl>

          <Button
            leftIcon={<FiFilter />}
            variant="subtle"
            onClick={() => setShowAdvancedFilters((s) => !s)}
          >
            Фильтры{hasActiveAdvancedFilters ? " • активны" : ""}
          </Button>
          {hasActiveAdvancedFilters ? (
            <Button variant="ghost" onClick={resetTaskFilters}>
              Сбросить фильтры
            </Button>
          ) : null}
        </HStack>

        <Collapse in={showAdvancedFilters} animateOpacity>
          <Box
            mt={4}
            display="grid"
            gridTemplateColumns={{ base: "1fr", md: "1fr 1fr", xl: "1fr 1fr 1fr 1fr" }}
            gap={3}
          >
            <FormControl>
              <FormLabel>Проект</FormLabel>
              <Select
                value={filters.projectId ?? ""}
                onChange={(e) => {
                  setFilters((prev) => ({
                    ...prev,
                    projectId: e.target.value
                      ? Number(e.target.value)
                      : undefined,
                    statusId: undefined,
                  }))
                  setPagination((prev) => ({ ...prev, pageIndex: 0 }))
                }}
              >
                <option value="">Все проекты</option>
                {projectGroups.map(([groupName, items]) => (
                  <optgroup key={groupName} label={groupName}>
                    {items.map((project) => (
                      <option key={project.id} value={project.id}>
                        {project.name}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </Select>
            </FormControl>

            <FormControl>
              <FormLabel>Департамент</FormLabel>
              <Select
                value={filters.departmentId ?? ""}
                onChange={(e) => {
                  setFilters((prev) => ({
                    ...prev,
                    departmentId: e.target.value
                      ? Number(e.target.value)
                      : undefined,
                  }))
                  setPagination((prev) => ({ ...prev, pageIndex: 0 }))
                }}
              >
                <option value="">Все департаменты</option>
                {departmentsData?.data.map((department) => (
                  <option key={department.id} value={department.id}>
                    {department.name}
                  </option>
                ))}
              </Select>
            </FormControl>

            <FormControl>
              <FormLabel>Состояние задачи</FormLabel>
              <Select
                value={filters.statusId ?? ""}
                onChange={(e) => {
                  setFilters((prev) => ({
                    ...prev,
                    statusId: e.target.value
                      ? Number(e.target.value)
                      : undefined,
                  }))
                  setPagination((prev) => ({ ...prev, pageIndex: 0 }))
                }}
              >
                <option value="">Все состояния</option>
                {(filterStatusesData?.data ?? []).map((status) => (
                  <option key={status.id} value={status.id}>
                    {status.name}
                  </option>
                ))}
              </Select>
            </FormControl>

            <FormControl>
              <FormLabel>Исполнитель</FormLabel>
              <Input
                size="sm"
                placeholder="Поиск исполнителя"
                value={assigneeSearch}
                onChange={(e) => setAssigneeSearch(e.target.value)}
                mb={2}
              />
              <Select
                value={filters.assigneeId ?? ""}
                onChange={(e) => {
                  setFilters((prev) => ({
                    ...prev,
                    assigneeId: e.target.value
                      ? Number(e.target.value)
                      : undefined,
                  }))
                  setPagination((prev) => ({ ...prev, pageIndex: 0 }))
                }}
              >
                <option value="">Все исполнители</option>
                {filteredAssigneeOptions.map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.full_name || user.email}
                  </option>
                ))}
              </Select>
            </FormControl>

            <FormControl>
              <FormLabel>Состояние по сроку</FormLabel>
              <Select
                value={filters.deadlineState ?? ""}
                onChange={(e) => {
                  setFilters((prev) => ({
                    ...prev,
                    deadlineState: e.target.value
                      ? (e.target.value as "green" | "yellow" | "red")
                      : undefined,
                  }))
                  setPagination((prev) => ({ ...prev, pageIndex: 0 }))
                }}
              >
                <option value="">Все</option>
                <option value="green">В срок</option>
                <option value="yellow">Критично</option>
                <option value="red">Просрочено</option>
              </Select>
            </FormControl>

            <FormControl>
              <FormLabel>Показывать завершённые</FormLabel>
              <Switch
                isChecked={filters.includeCompleted}
                onChange={(e) => {
                  setFilters((prev) => ({
                    ...prev,
                    includeCompleted: e.target.checked,
                  }))
                  setPagination((prev) => ({ ...prev, pageIndex: 0 }))
                }}
              />
            </FormControl>
          </Box>

          <HStack mt={3} spacing={2} flexWrap="wrap">
            {table.getAllLeafColumns().map((column) => (
              <Checkbox
                key={column.id}
                isChecked={column.getIsVisible()}
                onChange={column.getToggleVisibilityHandler()}
                size="sm"
              >
                {String(column.columnDef.header)}
              </Checkbox>
            ))}
          </HStack>
        </Collapse>

        <HStack mt={3} spacing={2}>
          <Badge bg="#E6F5EA" color="#1C6B35" borderRadius="full">
            <Icon as={FiCheckCircle} mr={1} /> В срок
          </Badge>
          <Badge bg="#FFF2D6" color="#A46200" borderRadius="full">
            <Icon as={FiClock} mr={1} /> Критично
          </Badge>
          <Badge bg="#FDE7E7" color="#A61B1B" borderRadius="full">
            <Icon as={FiAlertCircle} mr={1} /> Просрочено
          </Badge>
        </HStack>
      </Box>

      <Box
        borderWidth="1px"
        borderColor="ui.border"
        borderRadius="10px"
        overflow="hidden"
        bg={panelBg}
        boxShadow="sm"
      >
        <Box overflowX="auto" minW={0}>
          <Table size="sm" sx={{ tableLayout: "fixed" }}>
            <Thead>
              {table.getHeaderGroups().map((headerGroup) => (
                <Tr key={headerGroup.id}>
                  {headerGroup.headers.map((header) => {
                    const sorted = header.column.getIsSorted()
                    return (
                      <Th
                        key={header.id}
                        w={`${header.getSize()}px`}
                        minW={`${header.column.columnDef.minSize ?? 80}px`}
                        position="sticky"
                        top={0}
                        bg={tableHeaderBg}
                        zIndex={2}
                        py="6px"
                        userSelect="none"
                      >
                        <Box
                          display="flex"
                          alignItems="center"
                          justifyContent="space-between"
                          cursor={
                            header.column.getCanSort() ? "pointer" : "default"
                          }
                          onClick={
                            header.column.getCanSort()
                              ? header.column.getToggleSortingHandler()
                              : undefined
                          }
                          gap={1}
                          position="relative"
                        >
                          <Text
                            fontSize="xs"
                            textTransform="uppercase"
                            letterSpacing="0.03em"
                          >
                            {header.isPlaceholder
                              ? null
                              : flexRender(
                                  header.column.columnDef.header,
                                  header.getContext(),
                                )}
                          </Text>
                          <Text fontSize="xs" color="gray.500">
                            {sorted === "asc"
                              ? "▲"
                              : sorted === "desc"
                                ? "▼"
                                : ""}
                          </Text>
                        </Box>
                        {header.column.getCanResize() && (
                          <Box
                            onMouseDown={header.getResizeHandler()}
                            onTouchStart={header.getResizeHandler()}
                            position="absolute"
                            right={0}
                            top={0}
                            h="100%"
                            w="6px"
                            cursor="col-resize"
                            zIndex={3}
                          />
                        )}
                      </Th>
                    )
                  })}
                </Tr>
              ))}
            </Thead>
            <Tbody>
              {isLoading && (
                <Tr>
                  <Td colSpan={table.getAllLeafColumns().length}>
                    <Text py={4}>Загрузка...</Text>
                  </Td>
                </Tr>
              )}
              {!isLoading && table.getRowModel().rows.length === 0 && (
                <Tr>
                  <Td colSpan={table.getAllLeafColumns().length}>
                    <Text py={4}>Нет данных</Text>
                  </Td>
                </Tr>
              )}
              {!isLoading &&
                table.getRowModel().rows.map((row) => (
                  <Tr
                    key={row.id}
                    bg={deadlineRowColor(resolveDeadlineState(row.original))}
                    _hover={{
                      bg: deadlineRowHoverColor(resolveDeadlineState(row.original)),
                    }}
                    cursor="pointer"
                    onClick={() => {
                      setSelectedTaskId(row.original.id)
                      taskDrawer.onOpen()
                    }}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <Td
                        key={cell.id}
                        py="6px"
                        borderColor={rowBorderColor}
                      >
                        {flexRender(
                          cell.column.columnDef.cell,
                          cell.getContext(),
                        )}
                      </Td>
                    ))}
                  </Tr>
                ))}
            </Tbody>
          </Table>
        </Box>

        <HStack
          justify="space-between"
          p={3}
          borderTopWidth="1px"
          borderColor="ui.border"
          bg={panelBg}
        >
          <Text fontSize="sm" color={paginationTextColor}>
            {fromRow}-{toRow} из {totalRows}
          </Text>
          <HStack>
            <Select
              size="sm"
              value={pagination.pageSize}
              onChange={(e) =>
                setPagination({
                  pageIndex: 0,
                  pageSize: Number(e.target.value),
                })
              }
              w="110px"
            >
              {[10, 20, 50, 100].map((size) => (
                <option key={size} value={size}>
                  {size} / стр.
                </option>
              ))}
            </Select>
            <Button
              size="sm"
              onClick={() => table.previousPage()}
              isDisabled={!table.getCanPreviousPage()}
            >
              Назад
            </Button>
            <Text fontSize="sm">
              {pagination.pageIndex + 1} / {table.getPageCount()}
            </Text>
            <Button
              size="sm"
              onClick={() => table.nextPage()}
              isDisabled={!table.getCanNextPage()}
            >
              Вперёд
            </Button>
          </HStack>
        </HStack>
      </Box>

      <Drawer
        isOpen={taskDrawer.isOpen}
        placement="right"
        onClose={closeTaskDrawer}
        size="lg"
      >
        <DrawerOverlay />
          <DrawerContent
            maxW={{ base: "100vw", xl: "860px" }}
            bg={drawerBg}
            color={drawerTextColor}
          >
            <DrawerCloseButton />
            <DrawerHeader bg={drawerHeaderBg} borderBottomWidth="1px" borderColor="ui.border">
              <HStack justify="space-between" pr={10} gap={2}>
                <Text fontWeight="700" noOfLines={1}>
                  {selectedTask
                    ? selectedTask.project_name || `Проект #${selectedTask.project_id}`
                    : "Карточка задачи"}
                </Text>
                {selectedTask ? (
                  isEditingTask ? (
                    <HStack>
                      <Button
                        size="sm"
                        variant="primary"
                        onClick={() => updateMutation.mutate()}
                        isLoading={updateMutation.isPending}
                        isDisabled={
                          !taskEditor.title.trim() ||
                          !htmlToText(taskEditor.description).trim() ||
                          !taskEditor.due_date ||
                          !taskEditor.workflow_status_id
                        }
                      >
                        Сохранить
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => {
                          if (selectedTask) {
                            resetTaskEditorFromTask(selectedTask)
                          }
                          setEditFiles([])
                          setIsEditingTask(false)
                        }}
                      >
                        Отмена
                      </Button>
                    </HStack>
                  ) : (
                    <HStack>
                      {canSubmitReview ? (
                        <Button
                          size="sm"
                          variant="subtle"
                          onClick={() => submitReviewMutation.mutate()}
                          isLoading={submitReviewMutation.isPending}
                        >
                          На проверку
                        </Button>
                      ) : null}
                      {canCompleteTask ? (
                        <Button
                          size="sm"
                          variant="primary"
                          onClick={() => completeTaskMutation.mutate()}
                          isLoading={completeTaskMutation.isPending}
                        >
                          Завершить задачу
                        </Button>
                      ) : null}
                      {canEditTask ? (
                        <Button size="sm" variant="subtle" onClick={() => setIsEditingTask(true)}>
                          Редактировать
                        </Button>
                      ) : null}
                    </HStack>
                  )
                ) : null}
              </HStack>
            </DrawerHeader>
          <DrawerBody pb={5}>
            {selectedTaskLoading ? (
              <HStack py={4}>
                <Spinner size="sm" />
                <Text>Загрузка задачи…</Text>
              </HStack>
            ) : !selectedTask ? (
              <Text>Задача не найдена</Text>
            ) : (
              <VStack align="stretch" spacing={4}>
                <Box
                  borderWidth="1px"
                  borderColor="ui.border"
                  borderRadius="10px"
                  p={4}
                  bg={panelAltBg}
                >
                  <Grid templateColumns={{ base: "1fr", lg: "minmax(0, 3fr) minmax(0, 1fr)" }} gap={4}>
                    <Box minW={0}>
                      {isEditingTask ? (
                        <VStack align="stretch" spacing={3}>
                          <FormControl isRequired>
                            <FormLabel>Название задачи</FormLabel>
                            <Input
                              value={taskEditor.title}
                              onChange={(e) =>
                                setTaskEditor((prev) => ({
                                  ...prev,
                                  title: e.target.value,
                                }))
                              }
                            />
                          </FormControl>
                          <FormControl isRequired>
                            <FormLabel>Описание</FormLabel>
                            <RichTextEditor
                              value={taskEditor.description}
                              onChange={(next) =>
                                setTaskEditor((prev) => ({
                                  ...prev,
                                  description: next,
                                }))
                              }
                              minH="180px"
                            />
                          </FormControl>
                          <Grid templateColumns={{ base: "1fr", md: "1fr 1fr" }} gap={3}>
                            <FormControl isRequired>
                              <FormLabel>Состояние</FormLabel>
                              <Select
                                value={taskEditor.workflow_status_id}
                                onChange={(e) =>
                                  setTaskEditor((prev) => ({
                                    ...prev,
                                    workflow_status_id: Number(e.target.value),
                                  }))
                                }
                              >
                                {(selectedTaskStatuses?.data ?? []).map((status) => (
                                  <option key={status.id} value={status.id}>
                                    {status.name}
                                  </option>
                                ))}
                              </Select>
                            </FormControl>
                            <FormControl isRequired>
                              <FormLabel>Срок</FormLabel>
                              <Input
                                type="datetime-local"
                                value={taskEditor.due_date}
                                isDisabled={!canManageTaskControls}
                                onChange={(e) =>
                                  setTaskEditor((prev) => ({
                                    ...prev,
                                    due_date: e.target.value,
                                  }))
                                }
                              />
                            </FormControl>
                            <FormControl>
                              <FormLabel>Исполнитель</FormLabel>
                              <AssigneeMultiPicker
                                value={taskEditor.assignee_ids}
                                onChange={(next) =>
                                  setTaskEditor((prev) => ({
                                    ...prev,
                                    assignee_ids: next,
                                  }))
                                }
                                options={
                                  selectedTaskProjectMemberOptions.length
                                    ? selectedTaskProjectMemberOptions
                                    : memberOptions
                                }
                                isDisabled={!canManageTaskControls}
                                addButtonLabel="Добавить"
                              />
                            </FormControl>
                            <FormControl>
                              <HStack justify="space-between" mb={1} align="center">
                                <FormLabel mb={0}>Контроллер</FormLabel>
                                {canManageTaskControls ? (
                                  <Popover placement="bottom-end">
                                    <PopoverTrigger>
                                      <Button size="xs" variant="outline">
                                        Назначить только на задачу
                                      </Button>
                                    </PopoverTrigger>
                                    <PopoverContent maxW="340px" zIndex={1600}>
                                      <PopoverHeader fontWeight="700">
                                        Временный контроллер задачи
                                      </PopoverHeader>
                                      <PopoverBody>
                                        <VStack align="stretch" spacing={1} maxH="220px" overflowY="auto">
                                          {selectedTaskProjectMemberOptions.length === 0 ? (
                                            <Text fontSize="sm" color="ui.muted">
                                              Нет участников проекта
                                            </Text>
                                          ) : (
                                            selectedTaskProjectMemberOptions.map((member) => (
                                              <Button
                                                key={`task-controller-option-${member.id}`}
                                                variant="ghost"
                                                justifyContent="flex-start"
                                                onClick={() =>
                                                  setTaskEditor((prev) => ({
                                                    ...prev,
                                                    controller_id: String(member.id),
                                                  }))
                                                }
                                              >
                                                {member.label}
                                              </Button>
                                            ))
                                          )}
                                        </VStack>
                                      </PopoverBody>
                                    </PopoverContent>
                                  </Popover>
                                ) : null}
                              </HStack>
                              <Select
                                value={taskEditor.controller_id}
                                isDisabled={!canManageTaskControls}
                                onChange={(e) =>
                                  setTaskEditor((prev) => ({
                                    ...prev,
                                    controller_id: e.target.value,
                                  }))
                                }
                              >
                                <option value="">Не назначен</option>
                                {selectedTaskControllerOptions.map((member) => (
                                  <option key={`edit-controller-${member.id}`} value={member.id}>
                                    {member.label}
                                  </option>
                                ))}
                              </Select>
                            </FormControl>
                          </Grid>
                          {!canManageTaskControls ? (
                            <Text fontSize="sm" color="ui.muted">
                              Изменение срока и назначений доступно только контроллеру задачи или системному администратору.
                            </Text>
                          ) : null}
                          <FormControl>
                            <FormLabel>Вложения</FormLabel>
                            <Input
                              type="file"
                              multiple
                              onChange={(event) => {
                                const files = event.target.files
                                setEditFiles(files ? Array.from(files) : [])
                              }}
                            />
                            <HStack mt={2} justify="space-between" align="center">
                              <Text fontSize="xs" color="ui.muted">
                                {editFiles.length
                                  ? `Выбрано файлов: ${editFiles.length}`
                                  : "Можно прикрепить файлы при редактировании"}
                              </Text>
                              <Button
                                size="sm"
                                variant="subtle"
                                onClick={() => uploadEditAttachmentsMutation.mutate()}
                                isLoading={uploadEditAttachmentsMutation.isPending}
                                isDisabled={!selectedTaskId || editFiles.length === 0}
                              >
                                Загрузить файлы
                              </Button>
                            </HStack>
                          </FormControl>
                        </VStack>
                      ) : (
                        <>
                          <HStack justify="space-between" align="start" gap={3}>
                            <Box minW={0}>
                              <Text fontWeight="800" fontSize="lg" noOfLines={2}>
                                {selectedTask.title}
                              </Text>
                              <Text fontSize="sm" color="ui.muted">
                                {selectedTask.project_name || `Проект #${selectedTask.project_id}`}
                              </Text>
                            </Box>
                            <Badge colorScheme={deadlineBadgeColor(resolveDeadlineState(selectedTask))}>
                              {deadlineBadgeLabel(resolveDeadlineState(selectedTask))}
                            </Badge>
                          </HStack>
                          <Box mt={3}>
                            <RichTextContent
                              value={selectedTask.description}
                              fontSize="sm"
                              color="inherit"
                            />
                          </Box>
                        </>
                      )}
                    </Box>

                    <Box borderWidth="1px" borderColor="ui.border" borderRadius="8px" p={3}>
                      <Text fontSize="sm" fontWeight="700" mb={2}>
                        Данные задачи
                      </Text>
                      <VStack align="stretch" spacing={1.5}>
                        <HStack align="start" justify="space-between" gap={2}>
                          <Text fontSize="xs" fontWeight="700" color="ui.muted">
                            Состояние:
                          </Text>
                          <Text fontSize="sm" textAlign="right">
                            {selectedTask.status_name || selectedTask.workflow_status_name || "-"}
                          </Text>
                        </HStack>
                        <HStack align="start" justify="space-between" gap={2}>
                          <Text fontSize="xs" fontWeight="700" color="ui.muted">
                            Исполнители:
                          </Text>
                          <Text fontSize="sm" textAlign="right">
                            {selectedTask.assignee_names?.length
                              ? selectedTask.assignee_names.join(", ")
                              : selectedTask.assignee_name || "-"}
                          </Text>
                        </HStack>
                        <HStack align="start" justify="space-between" gap={2}>
                          <Text fontSize="xs" fontWeight="700" color="ui.muted">
                            Контроллер:
                          </Text>
                          <Text fontSize="sm" textAlign="right">
                            {selectedTask.controller_name || "-"}
                          </Text>
                        </HStack>
                        <HStack align="start" justify="space-between" gap={2}>
                          <Text fontSize="xs" fontWeight="700" color="ui.muted">
                            Департамент:
                          </Text>
                          <Text fontSize="sm" textAlign="right">
                            {selectedTask.department_name || "-"}
                          </Text>
                        </HStack>
                        <HStack align="start" justify="space-between" gap={2}>
                          <Text fontSize="xs" fontWeight="700" color="ui.muted">
                            Срок:
                          </Text>
                          <Text fontSize="sm" textAlign="right">
                            {formatDate(selectedTask.due_date)}
                          </Text>
                        </HStack>
                        <HStack align="start" justify="space-between" gap={2}>
                          <Text fontSize="xs" fontWeight="700" color="ui.muted">
                            Последняя активность:
                          </Text>
                          <Text fontSize="sm" textAlign="right">
                            {selectedTask.last_activity_at
                              ? formatDate(selectedTask.last_activity_at)
                              : "-"}
                          </Text>
                        </HStack>
                        <HStack align="start" justify="space-between" gap={2}>
                          <Text fontSize="xs" fontWeight="700" color="ui.muted">
                            Кто обновил:
                          </Text>
                          <Text fontSize="sm" textAlign="right">
                            {selectedTask.last_activity_by || "-"}
                          </Text>
                        </HStack>
                      </VStack>
                    </Box>
                  </Grid>
                </Box>

                <Box borderWidth="1px" borderColor="ui.border" borderRadius="10px" p={3} bg={panelAltBg}>
                  <Text fontWeight="700" mb={2}>
                    Комментарии ({selectedTaskComments?.count ?? 0})
                  </Text>
                  <VStack align="stretch" spacing={2}>
                    {(selectedTaskComments?.data ?? []).slice(0, 6).map((comment) => (
                      <Box key={comment.id} borderWidth="1px" borderColor="ui.border" borderRadius="8px" p={2.5}>
                        <Text fontSize="xs" color="ui.muted" mb={1}>
                          {comment.author_name || comment.author_email || `User #${comment.author_id}`}
                        </Text>
                        <Text fontSize="sm">{comment.comment}</Text>
                        <Text fontSize="xs" color="ui.muted">
                          {formatDateTime(comment.created_at)}
                        </Text>
                      </Box>
                    ))}
                    {!selectedTaskComments?.count && (
                      <Text fontSize="sm" color="ui.muted">
                        Комментариев пока нет
                      </Text>
                    )}
                  </VStack>
                  <HStack mt={3} align="start">
                    <Input
                      value={drawerComment}
                      onChange={(e) => setDrawerComment(e.target.value)}
                      placeholder="Добавить комментарий"
                    />
                    <Button
                      size="sm"
                      onClick={() => addCommentMutation.mutate()}
                      isLoading={addCommentMutation.isPending}
                      isDisabled={!drawerComment.trim()}
                    >
                      Отправить
                    </Button>
                  </HStack>
                </Box>

                <Accordion allowMultiple>
                  <AccordionItem borderWidth="1px" borderColor="ui.border" borderRadius="10px" mb={2}>
                    <h2>
                      <AccordionButton>
                        <Box flex="1" textAlign="left" fontWeight="700">
                          Вложения ({selectedTaskAttachments?.count ?? 0})
                        </Box>
                        <AccordionIcon />
                      </AccordionButton>
                    </h2>
                    <AccordionPanel pt={0}>
                      <VStack align="stretch" spacing={2}>
                        {(selectedTaskAttachments?.data ?? []).map((attachment) => (
                          <Box
                            key={attachment.id}
                            borderWidth="1px"
                            borderColor="ui.border"
                            borderRadius="8px"
                            px={3}
                            py={2}
                            bg={attachmentCardBg}
                          >
                            <HStack justify="space-between" align="center" gap={3}>
                              <Text fontSize="sm" noOfLines={1}>
                                {attachment.file_name}
                              </Text>
                              <Button
                                size="xs"
                                variant="subtle"
                                onClick={() =>
                                  downloadAttachment(attachment.id, attachment.file_name)
                                }
                              >
                                Скачать
                              </Button>
                            </HStack>
                          </Box>
                        ))}
                        {!selectedTaskAttachments?.count && (
                          <Text fontSize="sm" color="ui.muted">
                            Вложений нет
                          </Text>
                        )}
                      </VStack>
                    </AccordionPanel>
                  </AccordionItem>

                  <AccordionItem borderWidth="1px" borderColor="ui.border" borderRadius="10px">
                    <h2>
                      <AccordionButton>
                        <Box flex="1" textAlign="left" fontWeight="700">
                          История изменений ({selectedTaskHistory?.count ?? 0})
                        </Box>
                        <AccordionIcon />
                      </AccordionButton>
                    </h2>
                    <AccordionPanel pt={0}>
                      <VStack align="stretch" spacing={1.5}>
                        {(selectedTaskHistory?.data ?? []).map((item) => (
                          <Text key={item.id} fontSize="sm">
                            {formatDateTime(item.created_at)} •{" "}
                            {item.actor_name || `User #${item.actor_id}`} •{" "}
                            {humanizeAction(item.action)}{" "}
                            {item.field_name ? `(${item.field_name})` : ""}
                            {item.old_value || item.new_value
                              ? ` • ${item.old_value ?? "null"} -> ${item.new_value ?? "null"}`
                              : ""}
                          </Text>
                        ))}
                        {!selectedTaskHistory?.count && (
                          <Text fontSize="sm" color="ui.muted">
                            История пуста
                          </Text>
                        )}
                      </VStack>
                    </AccordionPanel>
                  </AccordionItem>
                </Accordion>
              </VStack>
            )}
          </DrawerBody>
        </DrawerContent>
      </Drawer>

      <Modal
        isOpen={modal.isOpen}
        onClose={closeCreateModal}
        size="4xl"
        isCentered
      >
        <ModalOverlay />
        <ModalContent borderRadius="10px">
          <ModalHeader>Создание задачи</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <Box display="grid" gridTemplateColumns="1fr" gap={3}>
              <FormControl isRequired>
                <FormLabel>Название задачи</FormLabel>
                <Input
                  value={form.title}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, title: e.target.value }))
                  }
                />
              </FormControl>

              <FormControl isRequired>
                <FormLabel>Описание задачи</FormLabel>
                <RichTextEditor
                  value={form.description}
                  onChange={(next) =>
                    setForm((prev) => ({
                      ...prev,
                      description: next,
                    }))
                  }
                  minH="220px"
                  placeholder="Используйте форматирование: жирный текст, списки, чек-листы"
                />
              </FormControl>

              <FormControl isRequired>
                <FormLabel>Проект</FormLabel>
                <Select
                  value={form.project_id}
                  onChange={(e) =>
                    setForm((prev) => ({
                      ...prev,
                      project_id: Number(e.target.value),
                      assignee_ids: [],
                      controller_id: "",
                    }))
                  }
                >
                  <option value={0} disabled>
                    Выберите проект
                  </option>
                  {projectsData?.data.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.name}
                    </option>
                  ))}
                </Select>
              </FormControl>

              {isRegularUser ? (
                <HStack spacing={2} justify="flex-start">
                  <Tooltip
                    hasArrow
                    placement="top-start"
                    label="Исполнитель назначается автоматически (вы сами), контроллер назначается системой по вашей группе."
                  >
                    <IconButton
                      aria-label="Как назначается задача"
                      icon={<FiInfo />}
                      size="xs"
                      variant="ghost"
                    />
                  </Tooltip>
                </HStack>
              ) : (
                <Box
                  display="grid"
                  gridTemplateColumns={{ base: "1fr", md: "1fr 1fr 1fr" }}
                  gap={3}
                >
                  <FormControl>
                    <FormLabel>Исполнитель</FormLabel>
                    <AssigneeMultiPicker
                      value={form.assignee_ids}
                      onChange={(next) =>
                        setForm((prev) => ({
                          ...prev,
                          assignee_ids: next,
                        }))
                      }
                      options={createMemberOptions}
                      isDisabled={!form.project_id}
                      addButtonLabel="Добавить"
                    />
                  </FormControl>

                  <FormControl>
                    <FormLabel>Контроллер</FormLabel>
                    <Select
                      value={form.controller_id}
                      onChange={(e) =>
                        setForm((prev) => ({
                          ...prev,
                          controller_id: e.target.value,
                        }))
                      }
                      isDisabled={!form.project_id}
                    >
                      <option value="">Не назначен</option>
                      {createControllerOptions.map((member) => (
                        <option key={`controller-${member.id}`} value={member.id}>
                          {member.label}
                        </option>
                      ))}
                    </Select>
                  </FormControl>
                </Box>
              )}

              <Box
                display="grid"
                gridTemplateColumns={{ base: "1fr", md: "1fr" }}
                gap={3}
              >
                <FormControl isRequired>
                  <FormLabel>Срок</FormLabel>
                  <Input
                    type="datetime-local"
                    value={form.due_date}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, due_date: e.target.value }))
                    }
                    />
                </FormControl>

                <FormControl>
                  <FormLabel>Вложения</FormLabel>
                  <Input
                    type="file"
                    multiple
                    onChange={(event) => {
                      const files = event.target.files
                      setCreateFiles(files ? Array.from(files) : [])
                    }}
                  />
                  <Text mt={1} fontSize="xs" color="ui.muted">
                    {createFiles.length
                      ? `Выбрано файлов: ${createFiles.length}`
                      : "Файлы можно прикрепить сразу при создании"}
                  </Text>
                </FormControl>
              </Box>
            </Box>
          </ModalBody>
          <ModalFooter gap={3}>
            <Button
              variant="primary"
              onClick={() => createMutation.mutate()}
              isLoading={createMutation.isPending}
              isDisabled={
                !form.title.trim() ||
                !plainDescription.trim() ||
                !form.project_id ||
                !form.due_date
              }
            >
              Создать
            </Button>
            <Button onClick={closeCreateModal}>Отмена</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
      <Outlet />
    </Container>
  )
}

function parseSmartQuery(
  query: string,
  data: {
    projects: Project[]
    users: TrackerUser[]
    statuses: ProjectStatus[]
    departments: Array<{ id: number; name: string }>
  },
): SmartQueryResult {
  if (!query.trim()) return {}

  const tokens = query.trim().split(/\s+/)
  const rest: string[] = []
  const result: SmartQueryResult = {}

  for (const token of tokens) {
    const [rawKey, ...rawValueParts] = token.split(":")
    if (!rawValueParts.length) {
      rest.push(token)
      continue
    }

    const key = rawKey.toLowerCase()
    const value = rawValueParts.join(":").trim()

    if (key === "project") {
      const numeric = Number(value)
      if (!Number.isNaN(numeric) && numeric > 0) {
        result.projectId = numeric
      } else {
        const match = data.projects.find((project) =>
          project.name.toLowerCase().includes(value.toLowerCase()),
        )
        if (match) result.projectId = match.id
      }
      continue
    }

    if (key === "assignee") {
      const numeric = Number(value)
      if (!Number.isNaN(numeric) && numeric > 0) {
        result.assigneeId = numeric
      } else {
        const match = data.users.find((user) => {
          const fullName = (user.full_name || "").toLowerCase()
          const email = user.email.toLowerCase()
          const queryValue = value.toLowerCase()
          return fullName.includes(queryValue) || email.includes(queryValue)
        })
        if (match) result.assigneeId = match.id
      }
      continue
    }

    if (key === "status") {
      const numeric = Number(value)
      if (!Number.isNaN(numeric) && numeric > 0) {
        result.statusId = numeric
      } else {
        const match = data.statuses.find((status) =>
          status.name.toLowerCase().includes(value.toLowerCase()),
        )
        if (match) result.statusId = match.id
      }
      continue
    }

    if (key === "department") {
      const numeric = Number(value)
      if (!Number.isNaN(numeric) && numeric > 0) {
        result.departmentId = numeric
      } else {
        const match = data.departments.find((department) =>
          department.name.toLowerCase().includes(value.toLowerCase()),
        )
        if (match) result.departmentId = match.id
      }
      continue
    }

    if (key === "overdue") {
      result.overdueOnly = ["1", "true", "yes", "y", "да"].includes(
        value.toLowerCase(),
      )
      continue
    }

    rest.push(token)
  }

  if (rest.length) {
    result.plainSearch = rest.join(" ")
  }

  return result
}

function formatDate(value: string): string {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "-"
  return date.toLocaleDateString()
}

function toDateTimeLocalValue(value: string): string {
  const date = new Date(value)
  const offsetMs = date.getTimezoneOffset() * 60_000
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16)
}

function formatDateTime(value: string): string {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "-"
  return date.toLocaleString()
}

function mapSortField(value: string): string {
  const mapping: Record<string, string> = {
    workflow_status_name: "status_name",
  }
  return mapping[value] || value
}

function parsePositiveInt(value: string | null): number | undefined {
  if (!value) return undefined
  const parsed = Number(value)
  if (!Number.isInteger(parsed) || parsed <= 0) return undefined
  return parsed
}

function deadlineBadgeColor(state: "green" | "yellow" | "red") {
  if (state === "red") return "red"
  if (state === "yellow") return "yellow"
  return "green"
}

function deadlineBadgeLabel(state: "green" | "yellow" | "red") {
  if (state === "red") return "Просрочено"
  if (state === "yellow") return "Критично"
  return "В срок"
}

function deadlineRowColor(state: "green" | "yellow" | "red") {
  if (state === "red") return "#FAD7D7"
  if (state === "yellow") return "#FFE7A8"
  return "#CDEFD8"
}

function deadlineRowHoverColor(state: "green" | "yellow" | "red") {
  if (state === "red") return "#F5C0C0"
  if (state === "yellow") return "#FFD97A"
  return "#B4E7C4"
}

function resolveDeadlineState(task: Task): "green" | "yellow" | "red" {
  if (task.closed_overdue) return "red"
  return task.computed_deadline_state
}

function humanizeAction(action: string): string {
  const map: Record<string, string> = {
    created: "Создание",
    updated: "Обновление",
    due_date_changed: "Изменён срок",
    status_changed: "Изменён статус",
    assignee_changed: "Изменён исполнитель",
    closed: "Закрытие",
    reopened: "Переоткрытие",
    comment_added: "Комментарий",
    attachment_added: "Вложение",
  }
  return map[action] || action
}
