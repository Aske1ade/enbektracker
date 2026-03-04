import {
  Badge,
  Box,
  Button,
  Container,
  Divider,
  FormControl,
  FormLabel,
  Grid,
  GridItem,
  HStack,
  Heading,
  Input,
  List,
  ListItem,
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
  Tooltip,
  Tr,
  useDisclosure,
  VStack,
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useEffect, useMemo, useRef, useState } from "react"

import useCustomToast from "../../hooks/useCustomToast"
import {
  type AdminUserUpdatePayload,
  trackerApi,
} from "../../services/trackerApi"
import type { TrackerUser } from "../../types/tracker"

export const Route = createFileRoute("/_layout/admin")({
  component: AdminPage,
})

type UserFormState = {
  email: string
  full_name: string
  password: string
  is_active: boolean
  is_superuser: boolean
  must_change_password: boolean
  system_role: "user" | "system_admin"
  department_id: string
  bind_project_id: string
  bind_project_role: "reader" | "contributor" | "project_admin"
}

type SortDirection = "asc" | "desc"
type AdminUserSortKey =
  | "id"
  | "full_name"
  | "email"
  | "role"
  | "department"
  | "is_active"
  | "is_superuser"
type DemoCredentialSortKey =
  | "username"
  | "email"
  | "full_name"
  | "system_role"
  | "department_name"

const emptyUserForm: UserFormState = {
  email: "",
  full_name: "",
  password: "",
  is_active: true,
  is_superuser: false,
  must_change_password: false,
  system_role: "user",
  department_id: "",
  bind_project_id: "",
  bind_project_role: "contributor",
}

const ROLE_META: Record<
  UserFormState["system_role"],
  { label: string; hint: string }
> = {
  user: {
    label: "Пользователь",
    hint: "Стандартный пользователь с доступом через назначения ролей в проектах.",
  },
  system_admin: {
    label: "Системный администратор",
    hint: "Полный доступ к администрированию системы и проектных настроек.",
  },
}

function normalizeSystemRole(
  role: string | undefined | null,
): UserFormState["system_role"] {
  if (role === "system_admin" || role === "admin" || role === "manager") {
    return "system_admin"
  }
  return "user"
}

function groupRoleLabel(role: string): string {
  if (role === "owner") return "Директор"
  if (role === "manager") return "Руководитель"
  if (role === "member") return "Участник"
  return role
}

function projectMemberRoleLabel(role: string): string {
  if (role === "reader") return "Читатель"
  if (role === "executor") return "Исполнитель"
  if (role === "controller") return "Контроллер"
  if (role === "manager") return "Менеджер проекта"
  return role
}

function compareText(a: string, b: string): number {
  return a.localeCompare(b, "ru", { sensitivity: "base" })
}

function sortMark(active: boolean, direction: SortDirection): string {
  if (!active) return "↕"
  return direction === "asc" ? "↑" : "↓"
}

function desktopAgentSourceLabel(
  source: "uploaded" | "local_path" | "redirect_url" | "none" | undefined,
): string {
  if (source === "uploaded") return "Загружен через админку (MinIO)"
  if (source === "local_path") return "Локальный файл на backend"
  if (source === "redirect_url") return "Внешняя ссылка"
  return "Не настроен"
}

function formatBytes(value?: number | null): string {
  if (!value || value <= 0) return "-"
  const mb = value / (1024 * 1024)
  if (mb >= 1024) return `${(mb / 1024).toFixed(2)} GB`
  return `${mb.toFixed(2)} MB`
}

function AdminPage() {
  const showToast = useCustomToast()
  const queryClient = useQueryClient()
  const createModal = useDisclosure()
  const editModal = useDisclosure()
  const accessMapModal = useDisclosure()
  const [search, setSearch] = useState("")
  const [userSort, setUserSort] = useState<{
    key: AdminUserSortKey
    direction: SortDirection
  }>({
    key: "id",
    direction: "desc",
  })
  const [demoSort, setDemoSort] = useState<{
    key: DemoCredentialSortKey
    direction: SortDirection
  }>({
    key: "email",
    direction: "asc",
  })
  const [newUser, setNewUser] = useState<UserFormState>(emptyUserForm)
  const [editingUser, setEditingUser] = useState<TrackerUser | null>(null)
  const [accessMapUser, setAccessMapUser] = useState<TrackerUser | null>(null)
  const [accessOrgId, setAccessOrgId] = useState("")
  const [accessGroupId, setAccessGroupId] = useState("")
  const [accessGroupRole, setAccessGroupRole] = useState<"owner" | "manager" | "member">("member")
  const [taskBulkOrgId, setTaskBulkOrgId] = useState("")
  const [taskBulkGroupId, setTaskBulkGroupId] = useState("")
  const [taskBulkProjectId, setTaskBulkProjectId] = useState("")
  const [taskBulkControllerId, setTaskBulkControllerId] = useState("")
  const [taskBulkIncludeCompleted, setTaskBulkIncludeCompleted] = useState(true)
  const [editForm, setEditForm] = useState<UserFormState>(emptyUserForm)
  const desktopAgentInputRef = useRef<HTMLInputElement | null>(null)

  const { data: usersData, isLoading } = useQuery({
    queryKey: ["admin-users"],
    queryFn: () => trackerApi.listUsers(),
  })

  const { data: departmentsData } = useQuery({
    queryKey: ["departments-for-admin"],
    queryFn: () => trackerApi.listDepartments(),
  })

  const { data: projectsData } = useQuery({
    queryKey: ["projects-for-admin-users"],
    queryFn: () =>
      trackerApi.listProjects({
        page: 1,
        page_size: 500,
        sort_by: "name",
        sort_order: "asc",
      }),
  })

  const { data: demoData, isLoading: demoDataLoading } = useQuery({
    queryKey: ["admin-demo-data"],
    queryFn: () => trackerApi.getDemoDataStatus(),
  })
  const { data: taskPolicy, isLoading: taskPolicyLoading } = useQuery({
    queryKey: ["admin-task-policy"],
    queryFn: () => trackerApi.getAdminTaskPolicy(),
  })
  const { data: desktopAgentData, isLoading: desktopAgentLoading } = useQuery({
    queryKey: ["admin-desktop-agent"],
    queryFn: () => trackerApi.getAdminDesktopAgent(),
  })
  const { data: organizationsForAccess } = useQuery({
    queryKey: ["admin-access-organizations"],
    queryFn: () => trackerApi.listOrganizations(),
  })
  const { data: groupsForAccess } = useQuery({
    queryKey: ["admin-access-groups", accessOrgId],
    queryFn: () => trackerApi.getOrganizationGroups(Number(accessOrgId)),
    enabled: accessMapModal.isOpen && Boolean(accessOrgId),
  })
  const { data: groupsForTaskBulk } = useQuery({
    queryKey: ["admin-task-bulk-groups", taskBulkOrgId],
    queryFn: () => trackerApi.getOrganizationGroups(Number(taskBulkOrgId)),
    enabled: Boolean(taskBulkOrgId),
  })
  const {
    data: accessMapData,
    isLoading: accessMapLoading,
    isFetching: accessMapFetching,
  } = useQuery({
    queryKey: ["admin-user-access-map", accessMapUser?.id],
    queryFn: () => trackerApi.getAdminUserAccessMap(accessMapUser!.id),
    enabled: Boolean(accessMapUser?.id && accessMapModal.isOpen),
  })

  useEffect(() => {
    setAccessGroupId("")
  }, [accessOrgId])

  useEffect(() => {
    setTaskBulkGroupId("")
  }, [taskBulkOrgId])

  const filteredUsers = useMemo(() => {
    const rows = usersData?.data ?? []
    if (!search.trim()) return rows
    const q = search.trim().toLowerCase()
    return rows.filter(
      (user) =>
        user.email.toLowerCase().includes(q) ||
        (user.full_name || "").toLowerCase().includes(q) ||
        (user.system_role || "").toLowerCase().includes(q) ||
        ROLE_META[normalizeSystemRole(user.system_role)].label
          .toLowerCase()
          .includes(q),
    )
  }, [usersData, search])

  const departmentsById = useMemo(
    () => new Map((departmentsData?.data ?? []).map((dep) => [dep.id, dep.name])),
    [departmentsData?.data],
  )

  const sortedUsers = useMemo(() => {
    const rows = [...filteredUsers]
    rows.sort((a, b) => {
      let cmp = 0
      switch (userSort.key) {
        case "id":
          cmp = a.id - b.id
          break
        case "full_name":
          cmp = compareText(a.full_name || "", b.full_name || "")
          break
        case "email":
          cmp = compareText(a.email, b.email)
          break
        case "role":
          cmp = compareText(
            ROLE_META[normalizeSystemRole(a.system_role)].label,
            ROLE_META[normalizeSystemRole(b.system_role)].label,
          )
          break
        case "department":
          cmp = compareText(
            departmentsById.get(a.department_id ?? -1) || "",
            departmentsById.get(b.department_id ?? -1) || "",
          )
          break
        case "is_active":
          cmp = Number(a.is_active) - Number(b.is_active)
          break
        case "is_superuser":
          cmp = Number(a.is_superuser) - Number(b.is_superuser)
          break
        default:
          cmp = 0
      }
      return userSort.direction === "asc" ? cmp : -cmp
    })
    return rows
  }, [departmentsById, filteredUsers, userSort])

  const sortedDemoCredentials = useMemo(() => {
    const rows = [...(demoData?.credentials ?? [])]
    rows.sort((a, b) => {
      let cmp = 0
      switch (demoSort.key) {
        case "username":
          cmp = compareText(a.username || "", b.username || "")
          break
        case "email":
          cmp = compareText(a.email, b.email)
          break
        case "full_name":
          cmp = compareText(a.full_name || "", b.full_name || "")
          break
        case "system_role":
          cmp = compareText(
            ROLE_META[normalizeSystemRole(a.system_role)].label,
            ROLE_META[normalizeSystemRole(b.system_role)].label,
          )
          break
        case "department_name":
          cmp = compareText(a.department_name || "", b.department_name || "")
          break
        default:
          cmp = 0
      }
      return demoSort.direction === "asc" ? cmp : -cmp
    })
    return rows
  }, [demoData?.credentials, demoSort])

  const toggleUserSort = (key: AdminUserSortKey) => {
    setUserSort((prev) =>
      prev.key === key
        ? { key, direction: prev.direction === "asc" ? "desc" : "asc" }
        : { key, direction: "asc" },
    )
  }

  const toggleDemoSort = (key: DemoCredentialSortKey) => {
    setDemoSort((prev) =>
      prev.key === key
        ? { key, direction: prev.direction === "asc" ? "desc" : "asc" }
        : { key, direction: "asc" },
    )
  }

  const currentUser = queryClient.getQueryData<TrackerUser>(["currentUser"])

  const upsertProjectAccessForUser = async ({
    projectId,
    userId,
    roleKey,
  }: {
    projectId: number
    userId: number
    roleKey: "reader" | "contributor" | "project_admin"
  }) => {
    const existing = await trackerApi.getProjectAccessUsers(projectId)
    const assignments = existing.data
      .filter((row) => row.user_id !== userId)
      .map((row) => ({
        user_id: row.user_id,
        role_key: row.role_key,
        is_active: row.is_active,
      }))
    assignments.push({
      user_id: userId,
      role_key: roleKey,
      is_active: true,
    })
    await trackerApi.replaceProjectAccessUsers(projectId, assignments)
  }

  const createMutation = useMutation({
    mutationFn: async (formState: UserFormState) => {
      const created = await trackerApi.adminCreateUser({
        email: formState.email,
        full_name: formState.full_name || undefined,
        password: formState.password,
        is_active: formState.is_active,
        is_superuser: formState.is_superuser,
        must_change_password: formState.must_change_password,
        system_role: formState.system_role,
        department_id: formState.department_id
          ? Number(formState.department_id)
          : null,
      })
      if (formState.bind_project_id) {
        await upsertProjectAccessForUser({
          projectId: Number(formState.bind_project_id),
          userId: created.id,
          roleKey: formState.bind_project_role,
        })
      }
      return created
    },
    onSuccess: () => {
      showToast.success("Успешно", "Пользователь создан")
      createModal.onClose()
      setNewUser(emptyUserForm)
      queryClient.invalidateQueries({ queryKey: ["admin-users"] })
      queryClient.invalidateQueries({ queryKey: ["project-access-users"] })
    },
    onError: (error) =>
      showToast.error("Не удалось создать пользователя", error),
  })

  const updateMutation = useMutation({
    mutationFn: ({
      userId,
      payload,
    }: {
      userId: number
      payload: AdminUserUpdatePayload
    }) => trackerApi.adminUpdateUser(userId, payload),
    onSuccess: () => {
      showToast.success("Успешно", "Пользователь обновлён")
      editModal.onClose()
      setEditingUser(null)
      queryClient.invalidateQueries({ queryKey: ["admin-users"] })
    },
    onError: (error) =>
      showToast.error("Не удалось обновить пользователя", error),
  })

  const deleteMutation = useMutation({
    mutationFn: (userId: number) => trackerApi.adminDeleteUser(userId),
    onSuccess: () => {
      showToast.success("Успешно", "Пользователь удалён")
      queryClient.invalidateQueries({ queryKey: ["admin-users"] })
    },
    onError: (error) =>
      showToast.error("Не удалось удалить пользователя", error),
  })

  const desktopTestMutation = useMutation({
    mutationFn: ({
      userId,
      mode,
    }: {
      userId: number
      mode: "single" | "full"
    }) => trackerApi.adminSendDesktopEventsTest(userId, mode),
    onSuccess: (result) => {
      showToast.success(
        "Тестовые события отправлены",
        `Создано desktop-событий: ${result.created_count}`,
      )
    },
    onError: (error) =>
      showToast.error("Не удалось отправить тестовые события", error),
  })

  const demoDataMutation = useMutation({
    mutationFn: (payload: { enabled: boolean; admin_password?: string }) =>
      trackerApi.setDemoDataEnabled(payload.enabled, {
        admin_password: payload.admin_password,
      }),
    onSuccess: (data, payload) => {
      queryClient.setQueryData(["admin-demo-data"], data)
      queryClient.invalidateQueries({ queryKey: ["admin-users"] })
      queryClient.invalidateQueries({ queryKey: ["departments-for-admin"] })
      queryClient.invalidateQueries({ queryKey: ["projects-for-calendar"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard-projects"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard-departments"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard-trends"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard-report-rows"] })
      queryClient.invalidateQueries({ queryKey: ["reports-projects"] })
      queryClient.invalidateQueries({ queryKey: ["reports-users"] })
      queryClient.invalidateQueries({ queryKey: ["reports-departments"] })
      queryClient.invalidateQueries({ queryKey: ["report-tasks"] })
      queryClient.invalidateQueries({ queryKey: ["tasks-list"] })
      queryClient.invalidateQueries({ queryKey: ["projects-list"] })
      queryClient.invalidateQueries({ queryKey: ["projects-list-for-tasks"] })
      queryClient.invalidateQueries({ queryKey: ["calendar-summary"] })
      queryClient.invalidateQueries({ queryKey: ["calendar-day"] })

      if (payload.enabled) {
        showToast.success("Успешно", "Система заполнена демо-данными")
      } else {
        showToast.success("Успешно", "Демо-данные удалены")
      }
    },
    onError: (error) =>
      showToast.error("Не удалось переключить демо-данные", error),
  })

  const demoDataLockMutation = useMutation({
    mutationFn: (is_locked: boolean) => trackerApi.setDemoDataLock(is_locked),
    onSuccess: (data) => {
      queryClient.setQueryData(["admin-demo-data"], data)
      showToast.success(
        "Успешно",
        data.is_locked
          ? "Защита демо-данных включена"
          : "Защита демо-данных выключена",
      )
    },
    onError: (error) =>
      showToast.error("Не удалось обновить защиту демо-данных", error),
  })

  const taskPolicyMutation = useMutation({
    mutationFn: (allow_backdated_creation: boolean) =>
      trackerApi.updateAdminTaskPolicy({ allow_backdated_creation }),
    onSuccess: (data) => {
      queryClient.setQueryData(["admin-task-policy"], data)
      showToast.success("Успешно", "Политика создания задач обновлена")
    },
    onError: (error) =>
      showToast.error("Не удалось обновить политику задач", error),
  })

  const bulkDeleteTasksMutation = useMutation({
    mutationFn: (payload: {
      project_id?: number
      group_id?: number
      organization_id?: number
      include_completed: boolean
    }) => trackerApi.adminBulkDeleteTasks(payload),
    onSuccess: (result) => {
      showToast.success(
        "Успешно",
        `Удалено задач: ${result.deleted_tasks} (в выборке: ${result.matched_tasks})`,
      )
      queryClient.invalidateQueries({ queryKey: ["tasks-list"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard-trends"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard-distributions"] })
      queryClient.invalidateQueries({ queryKey: ["projects-list"] })
      queryClient.invalidateQueries({ queryKey: ["projects-for-admin-users"] })
      queryClient.invalidateQueries({ queryKey: ["report-tasks"] })
    },
    onError: (error) =>
      showToast.error("Не удалось удалить задачи по выбранному контуру", error),
  })

  const bulkSetControllerMutation = useMutation({
    mutationFn: (payload: {
      controller_id: number
      project_id?: number
      group_id?: number
      organization_id?: number
      include_completed: boolean
    }) => trackerApi.adminBulkSetTaskController(payload),
    onSuccess: (result) => {
      showToast.success(
        "Успешно",
        `Контроллер обновлён у задач: ${result.updated_tasks} (в выборке: ${result.matched_tasks})`,
      )
      queryClient.invalidateQueries({ queryKey: ["tasks-list"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard-trends"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard-distributions"] })
    },
    onError: (error) =>
      showToast.error("Не удалось назначить контроллера для задач контура", error),
  })

  const uploadDesktopAgentMutation = useMutation({
    mutationFn: (file: File) => trackerApi.uploadAdminDesktopAgent(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-desktop-agent"] })
      showToast.success("Успешно", "Desktop-агент загружен")
    },
    onError: (error) =>
      showToast.error("Не удалось загрузить desktop-агент", error),
  })

  const clearDesktopAgentMutation = useMutation({
    mutationFn: () => trackerApi.clearAdminDesktopAgent(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-desktop-agent"] })
      showToast.success("Успешно", "Загруженный desktop-агент удалён")
    },
    onError: (error) =>
      showToast.error("Не удалось удалить desktop-агент", error),
  })

  const refreshAccessMap = () => {
    if (accessMapUser?.id) {
      queryClient.invalidateQueries({
        queryKey: ["admin-user-access-map", accessMapUser.id],
      })
    }
    queryClient.invalidateQueries({ queryKey: ["admin-users"] })
  }

  const addGroupMembershipMutation = useMutation({
    mutationFn: (payload: {
      groupId: number
      userId: number
      roleName: "owner" | "manager" | "member"
    }) =>
      trackerApi.addOrganizationGroupMember(payload.groupId, {
        user_id: payload.userId,
        role_name: payload.roleName,
      }),
    onSuccess: () => {
      showToast.success("Успешно", "Пользователь добавлен в группу")
      refreshAccessMap()
    },
    onError: (error) =>
      showToast.error("Не удалось добавить пользователя в группу", error),
  })

  const updateGroupMembershipMutation = useMutation({
    mutationFn: (payload: {
      groupId: number
      userId: number
      patch: Partial<{ role_name: "owner" | "manager" | "member"; is_active: boolean }>
    }) =>
      trackerApi.updateOrganizationGroupMember(
        payload.groupId,
        payload.userId,
        payload.patch,
      ),
    onSuccess: () => {
      showToast.success("Успешно", "Членство группы обновлено")
      refreshAccessMap()
    },
    onError: (error) =>
      showToast.error("Не удалось обновить членство группы", error),
  })

  const removeGroupMembershipMutation = useMutation({
    mutationFn: (payload: { groupId: number; userId: number }) =>
      trackerApi.removeOrganizationGroupMember(payload.groupId, payload.userId),
    onSuccess: () => {
      showToast.success("Успешно", "Членство группы удалено")
      refreshAccessMap()
    },
    onError: (error) =>
      showToast.error("Не удалось удалить членство группы", error),
  })

  return (
    <Container maxW="full" py={6}>
      <HStack justify="space-between" mb={4} align="start">
        <Box>
          <Heading size="lg" mb={1}>
            Администрирование пользователей
          </Heading>
          <Text color="gray.600">
            Управление ролями, департаментами и активностью пользователей
          </Text>
        </Box>
        <Button onClick={createModal.onOpen}>Добавить пользователя</Button>
      </HStack>

      <Box
        borderWidth="1px"
        borderColor="ui.border"
        borderRadius="md"
        p={4}
        bg="white"
        mb={4}
      >
        <HStack justify="space-between" align="center" mb={3}>
          <Box>
            <Text fontWeight="700">Политика задач</Text>
            <Text color="gray.600" fontSize="sm">
              Разрешение на создание задач со сроком в прошлом
            </Text>
          </Box>
          <FormControl
            display="flex"
            alignItems="center"
            justifyContent="flex-end"
            maxW="420px"
          >
            <FormLabel m={0} mr={3}>
              Разрешить создавать задачи задним числом
            </FormLabel>
            <Switch
              isChecked={Boolean(taskPolicy?.allow_backdated_creation)}
              isDisabled={taskPolicyLoading || taskPolicyMutation.isPending}
              onChange={(event) =>
                taskPolicyMutation.mutate(event.target.checked)
              }
            />
          </FormControl>
        </HStack>
      </Box>

      <Box
        borderWidth="1px"
        borderColor="ui.border"
        borderRadius="md"
        p={4}
        bg="white"
        mb={4}
      >
        <Text fontWeight="700" mb={1}>
          Массовые действия по задачам
        </Text>
        <Text color="gray.600" fontSize="sm" mb={3}>
          Админ может массово назначить контроллера или удалить задачи в контуре организации/группы/проекта.
        </Text>
        <Grid templateColumns={{ base: "1fr", md: "repeat(4, 1fr)" }} gap={3} mb={3}>
          <FormControl>
            <FormLabel>Организация</FormLabel>
            <Select
              value={taskBulkOrgId}
              onChange={(event) => setTaskBulkOrgId(event.target.value)}
            >
              <option value="">Не выбрано</option>
              {(organizationsForAccess?.data ?? []).map((org) => (
                <option key={org.id} value={org.id}>
                  {org.name}
                </option>
              ))}
            </Select>
          </FormControl>
          <FormControl isDisabled={!taskBulkOrgId}>
            <FormLabel>Группа</FormLabel>
            <Select
              value={taskBulkGroupId}
              onChange={(event) => setTaskBulkGroupId(event.target.value)}
            >
              <option value="">Не выбрано</option>
              {(groupsForTaskBulk?.data ?? []).map((group) => (
                <option key={group.id} value={group.id}>
                  {group.name}
                </option>
              ))}
            </Select>
          </FormControl>
          <FormControl>
            <FormLabel>Проект</FormLabel>
            <Select
              value={taskBulkProjectId}
              onChange={(event) => setTaskBulkProjectId(event.target.value)}
            >
              <option value="">Не выбрано</option>
              {(projectsData?.data ?? []).map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </Select>
          </FormControl>
          <FormControl>
            <FormLabel>Новый контроллер</FormLabel>
            <Select
              value={taskBulkControllerId}
              onChange={(event) => setTaskBulkControllerId(event.target.value)}
            >
              <option value="">Не выбрано</option>
              {(usersData?.data ?? [])
                .filter((user) => user.is_active)
                .map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.full_name || user.email}
                  </option>
                ))}
            </Select>
          </FormControl>
        </Grid>
        <HStack justify="space-between" flexWrap="wrap" gap={3}>
          <FormControl display="flex" alignItems="center" maxW="300px">
            <FormLabel m={0} mr={3}>
              Включать завершённые задачи
            </FormLabel>
            <Switch
              isChecked={taskBulkIncludeCompleted}
              onChange={(event) => setTaskBulkIncludeCompleted(event.target.checked)}
            />
          </FormControl>
          <HStack>
            <Button
              variant="outline"
              isDisabled={!taskBulkControllerId}
              isLoading={bulkSetControllerMutation.isPending}
              onClick={() =>
                bulkSetControllerMutation.mutate({
                  controller_id: Number(taskBulkControllerId),
                  project_id: taskBulkProjectId ? Number(taskBulkProjectId) : undefined,
                  group_id: taskBulkGroupId ? Number(taskBulkGroupId) : undefined,
                  organization_id: taskBulkOrgId ? Number(taskBulkOrgId) : undefined,
                  include_completed: taskBulkIncludeCompleted,
                })
              }
            >
              Назначить контроллера
            </Button>
            <Button
              colorScheme="red"
              isLoading={bulkDeleteTasksMutation.isPending}
              onClick={() => {
                const confirmed = window.confirm(
                  "Удалить задачи по выбранному контуру? Это действие необратимо.",
                )
                if (!confirmed) return
                bulkDeleteTasksMutation.mutate({
                  project_id: taskBulkProjectId ? Number(taskBulkProjectId) : undefined,
                  group_id: taskBulkGroupId ? Number(taskBulkGroupId) : undefined,
                  organization_id: taskBulkOrgId ? Number(taskBulkOrgId) : undefined,
                  include_completed: taskBulkIncludeCompleted,
                })
              }}
            >
              Удалить задачи
            </Button>
          </HStack>
        </HStack>
      </Box>

      <Box
        borderWidth="1px"
        borderColor="ui.border"
        borderRadius="md"
        p={4}
        bg="white"
        mb={4}
      >
        <HStack justify="space-between" align="start" mb={3} flexWrap="wrap" gap={3}>
          <Box>
            <Text fontWeight="700">Desktop-агент</Text>
            <Text color="gray.600" fontSize="sm">
              Администратор загружает `.exe` или `.msi`, пользователи скачивают через сервер
            </Text>
          </Box>
          <HStack>
            <input
              ref={desktopAgentInputRef}
              type="file"
              accept=".exe,.msi,application/x-msdownload,application/x-msi"
              style={{ display: "none" }}
              onChange={(event) => {
                const file = event.target.files?.[0]
                if (!file) return
                uploadDesktopAgentMutation.mutate(file)
                event.target.value = ""
              }}
            />
            <Button
              onClick={() => desktopAgentInputRef.current?.click()}
              isLoading={uploadDesktopAgentMutation.isPending}
              isDisabled={desktopAgentLoading || clearDesktopAgentMutation.isPending}
            >
              Загрузить EXE/MSI
            </Button>
            <Button
              variant="outline"
              colorScheme="red"
              onClick={() => clearDesktopAgentMutation.mutate()}
              isLoading={clearDesktopAgentMutation.isPending}
              isDisabled={
                desktopAgentLoading ||
                uploadDesktopAgentMutation.isPending ||
                desktopAgentData?.source !== "uploaded"
              }
            >
              Удалить загруженный файл
            </Button>
          </HStack>
        </HStack>

        <Grid templateColumns={{ base: "1fr", md: "repeat(4, 1fr)" }} gap={3}>
          <Box>
            <Text fontSize="xs" color="gray.500" textTransform="uppercase">
              Источник
            </Text>
            <Text fontWeight="600">
              {desktopAgentSourceLabel(desktopAgentData?.source)}
            </Text>
          </Box>
          <Box>
            <Text fontSize="xs" color="gray.500" textTransform="uppercase">
              Файл
            </Text>
            <Text fontWeight="600">{desktopAgentData?.file_name || "-"}</Text>
          </Box>
          <Box>
            <Text fontSize="xs" color="gray.500" textTransform="uppercase">
              Размер
            </Text>
            <Text fontWeight="600">{formatBytes(desktopAgentData?.size_bytes)}</Text>
          </Box>
          <Box>
            <Text fontSize="xs" color="gray.500" textTransform="uppercase">
              Загружен
            </Text>
            <Text fontWeight="600">
              {desktopAgentData?.uploaded_at
                ? new Date(desktopAgentData.uploaded_at).toLocaleString()
                : "-"}
            </Text>
          </Box>
        </Grid>
      </Box>

      <Box
        borderWidth="1px"
        borderColor="ui.border"
        borderRadius="md"
        p={4}
        bg="white"
        mb={4}
      >
        <HStack justify="space-between" align="start" mb={3}>
          <Box>
            <Text fontWeight="700">Демо-данные системы</Text>
            <Text color="gray.600" fontSize="sm">
              Переключатель создаёт/удаляет только тестовые сущности демо-набора{" "}
              <b>{demoData?.marker || "Текущий batch"}</b>
            </Text>
          </Box>
          <FormControl
            display="flex"
            alignItems="center"
            justifyContent="flex-end"
            maxW="320px"
          >
            <FormLabel m={0} mr={3}>
              Заполнить тестовыми данными
            </FormLabel>
            <Switch
              isChecked={Boolean(demoData?.enabled)}
              isDisabled={
                demoDataLoading ||
                demoDataMutation.isPending ||
                demoDataLockMutation.isPending
              }
              onChange={(event) => {
                const enabled = event.target.checked
                if (!enabled && demoData?.is_locked) {
                  const password = window.prompt(
                    "Демо-данные защищены. Введите пароль текущего администратора для удаления:",
                  )
                  if (!password) {
                    return
                  }
                  demoDataMutation.mutate({
                    enabled,
                    admin_password: password,
                  })
                  return
                }
                demoDataMutation.mutate({ enabled })
              }}
            />
          </FormControl>
        </HStack>

        <HStack justify="flex-end" mb={3}>
          <FormControl
            display="flex"
            alignItems="center"
            justifyContent="flex-end"
            maxW="420px"
          >
            <FormLabel m={0} mr={3}>
              Защитить демо-данные от случайного удаления
            </FormLabel>
            <Switch
              isChecked={Boolean(demoData?.is_locked)}
              isDisabled={
                demoDataLoading ||
                demoDataMutation.isPending ||
                demoDataLockMutation.isPending
              }
              onChange={(event) =>
                demoDataLockMutation.mutate(event.target.checked)
              }
            />
          </FormControl>
        </HStack>

        <HStack spacing={2} flexWrap="wrap" mb={3}>
          <Badge borderRadius="sm" colorScheme="blue">
            Департаменты: {demoData?.departments_count ?? 0}
          </Badge>
          <Badge borderRadius="sm" colorScheme="purple">
            Пользователи: {demoData?.users_count ?? 0}
          </Badge>
          <Badge borderRadius="sm" colorScheme="cyan">
            Проекты: {demoData?.projects_count ?? 0}
          </Badge>
          <Badge borderRadius="sm" colorScheme="orange">
            Задачи: {demoData?.tasks_count ?? 0}
          </Badge>
        </HStack>

        {Boolean(demoData?.enabled) &&
          (demoData?.credentials?.length ?? 0) > 0 && (
            <Box borderWidth="1px" borderColor="ui.border" borderRadius="md">
              <Box px={3} py={2} borderBottomWidth="1px" bg="gray.50">
                <Text fontWeight="600" fontSize="sm">
                  Готовые demo-пользователи для показа
                </Text>
              </Box>
              <Box overflowX="auto">
                <Table size="sm">
                  <Thead>
                    <Tr>
                      <Th>
                        <Button size="xs" variant="ghost" onClick={() => toggleDemoSort("username")}>
                          Логин {sortMark(demoSort.key === "username", demoSort.direction)}
                        </Button>
                      </Th>
                      <Th>
                        <Button size="xs" variant="ghost" onClick={() => toggleDemoSort("email")}>
                          Email {sortMark(demoSort.key === "email", demoSort.direction)}
                        </Button>
                      </Th>
                      <Th>
                        <Button size="xs" variant="ghost" onClick={() => toggleDemoSort("full_name")}>
                          ФИО {sortMark(demoSort.key === "full_name", demoSort.direction)}
                        </Button>
                      </Th>
                      <Th>
                        <Button
                          size="xs"
                          variant="ghost"
                          onClick={() => toggleDemoSort("system_role")}
                        >
                          Роль {sortMark(demoSort.key === "system_role", demoSort.direction)}
                        </Button>
                      </Th>
                      <Th>
                        <Button
                          size="xs"
                          variant="ghost"
                          onClick={() => toggleDemoSort("department_name")}
                        >
                          Департамент {sortMark(demoSort.key === "department_name", demoSort.direction)}
                        </Button>
                      </Th>
                      <Th>Организации</Th>
                      <Th>Группы</Th>
                      <Th>Роли в группах</Th>
                      <Th>Пароль</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {sortedDemoCredentials.map((credential) => (
                      <Tr key={credential.email}>
                        <Td>{credential.username || "-"}</Td>
                        <Td>{credential.email}</Td>
                        <Td>{credential.full_name || "-"}</Td>
                        <Td>
                          <Tooltip
                            label={
                              ROLE_META[normalizeSystemRole(credential.system_role)]
                                .hint
                            }
                            hasArrow
                            placement="top-start"
                          >
                            <Text as="span" cursor="help">
                              {
                                ROLE_META[normalizeSystemRole(credential.system_role)]
                                  .label
                              }
                            </Text>
                          </Tooltip>
                        </Td>
                        <Td>{credential.department_name || "-"}</Td>
                        <Td>
                          {credential.organization_names?.length ? (
                            <Text maxW="220px" noOfLines={2}>
                              {credential.organization_names.join(", ")}
                            </Text>
                          ) : (
                            "-"
                          )}
                        </Td>
                        <Td>
                          {credential.group_names?.length ? (
                            <Text maxW="260px" noOfLines={2}>
                              {credential.group_names.join(", ")}
                            </Text>
                          ) : (
                            "-"
                          )}
                        </Td>
                        <Td>
                          {credential.group_roles?.length ? (
                            <HStack spacing={1} flexWrap="wrap">
                              {credential.group_roles.map((roleName) => (
                                <Badge key={`${credential.email}-${roleName}`} borderRadius="sm">
                                  {groupRoleLabel(roleName)}
                                </Badge>
                              ))}
                            </HStack>
                          ) : (
                            "-"
                          )}
                        </Td>
                        <Td>
                          <Badge borderRadius="sm" colorScheme="green">
                            {credential.password}
                          </Badge>
                        </Td>
                      </Tr>
                    ))}
                  </Tbody>
                </Table>
              </Box>
            </Box>
          )}
      </Box>

      <Box
        borderWidth="1px"
        borderColor="ui.border"
        borderRadius="md"
        p={4}
        bg="white"
        mb={4}
      >
        <Grid templateColumns={{ base: "1fr", md: "1fr 220px" }} gap={3}>
          <GridItem>
            <FormControl>
              <FormLabel>Поиск</FormLabel>
              <Input
                placeholder="email / ФИО / роль"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </FormControl>
          </GridItem>
          <GridItem>
            <Text fontSize="xs" color="ui.muted" mt={8}>
              Найдено: {filteredUsers.length}
            </Text>
          </GridItem>
        </Grid>
      </Box>

      <Box
        borderWidth="1px"
        borderColor="ui.border"
        borderRadius="md"
        overflow="hidden"
        bg="white"
      >
        <Box overflowX="auto">
          <Table size="sm">
            <Thead>
              <Tr>
                <Th>
                  <Button size="xs" variant="ghost" onClick={() => toggleUserSort("id")}>
                    ID {sortMark(userSort.key === "id", userSort.direction)}
                  </Button>
                </Th>
                <Th>
                  <Button size="xs" variant="ghost" onClick={() => toggleUserSort("full_name")}>
                    Пользователь {sortMark(userSort.key === "full_name", userSort.direction)}
                  </Button>
                </Th>
                <Th>
                  <Button size="xs" variant="ghost" onClick={() => toggleUserSort("email")}>
                    Email {sortMark(userSort.key === "email", userSort.direction)}
                  </Button>
                </Th>
                <Th>
                  <Button size="xs" variant="ghost" onClick={() => toggleUserSort("role")}>
                    Роль {sortMark(userSort.key === "role", userSort.direction)}
                  </Button>
                </Th>
                <Th>
                  <Button size="xs" variant="ghost" onClick={() => toggleUserSort("department")}>
                    Департамент {sortMark(userSort.key === "department", userSort.direction)}
                  </Button>
                </Th>
                <Th>
                  <Button size="xs" variant="ghost" onClick={() => toggleUserSort("is_active")}>
                    Статус {sortMark(userSort.key === "is_active", userSort.direction)}
                  </Button>
                </Th>
                <Th>
                  <Button size="xs" variant="ghost" onClick={() => toggleUserSort("is_superuser")}>
                    Admin {sortMark(userSort.key === "is_superuser", userSort.direction)}
                  </Button>
                </Th>
                <Th>Действия</Th>
              </Tr>
            </Thead>
            <Tbody>
              {isLoading && (
                <Tr>
                  <Td colSpan={8}>Загрузка...</Td>
                </Tr>
              )}
              {!isLoading &&
                sortedUsers.map((user) => (
                  <Tr key={user.id}>
                    <Td>{user.id}</Td>
                    <Td>{user.full_name || "-"}</Td>
                    <Td>{user.email}</Td>
                    <Td>
                      <Tooltip
                        label={
                          ROLE_META[normalizeSystemRole(user.system_role)].hint
                        }
                        hasArrow
                        placement="top-start"
                      >
                        <Text as="span" cursor="help">
                          {ROLE_META[normalizeSystemRole(user.system_role)].label}
                        </Text>
                      </Tooltip>
                    </Td>
                    <Td>
                      {departmentsById.get(user.department_id ?? -1) || "-"}
                    </Td>
                    <Td>
                      <Badge
                        borderRadius="sm"
                        colorScheme={user.is_active ? "green" : "gray"}
                      >
                        {user.is_active ? "Активен" : "Отключён"}
                      </Badge>
                    </Td>
                    <Td>{user.is_superuser ? "Да" : "Нет"}</Td>
                    <Td>
                      <HStack spacing={2}>
                        <Button
                          size="xs"
                          variant="outline"
                          onClick={() => {
                            setAccessMapUser(user)
                            accessMapModal.onOpen()
                          }}
                        >
                          Доступы
                        </Button>
                        <Button
                          size="xs"
                          colorScheme="blue"
                          variant="outline"
                          onClick={() =>
                            desktopTestMutation.mutate({
                              userId: user.id,
                              mode: "full",
                            })
                          }
                          isLoading={
                            desktopTestMutation.isPending &&
                            desktopTestMutation.variables?.userId === user.id
                          }
                        >
                          Тест desktop
                        </Button>
                        <Button
                          size="xs"
                          variant="subtle"
                          onClick={() => {
                            setEditingUser(user)
                            setEditForm({
                              email: user.email,
                              full_name: user.full_name || "",
                              password: "",
                              is_active: user.is_active,
                              is_superuser: user.is_superuser,
                              must_change_password: Boolean(user.must_change_password),
                              system_role: normalizeSystemRole(user.system_role),
                              department_id: user.department_id
                                ? String(user.department_id)
                                : "",
                              bind_project_id: "",
                              bind_project_role: "contributor",
                            })
                            editModal.onOpen()
                          }}
                        >
                          Изменить
                        </Button>
                        <Button
                          size="xs"
                          colorScheme="red"
                          variant="outline"
                          onClick={() => deleteMutation.mutate(user.id)}
                          isLoading={deleteMutation.isPending}
                          isDisabled={user.id === currentUser?.id}
                        >
                          Удалить
                        </Button>
                      </HStack>
                    </Td>
                  </Tr>
                ))}
            </Tbody>
          </Table>
        </Box>
      </Box>

      <Modal isOpen={createModal.isOpen} onClose={createModal.onClose}>
        <ModalOverlay />
        <ModalContent borderRadius="md">
          <ModalHeader>Новый пользователь</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <UserForm
              value={newUser}
              departments={departmentsData?.data ?? []}
              projects={projectsData?.data ?? []}
              onChange={setNewUser}
              isEdit={false}
            />
          </ModalBody>
          <ModalFooter gap={3}>
            <Button
              onClick={() => createMutation.mutate(newUser)}
              isLoading={createMutation.isPending}
              isDisabled={!newUser.email || !newUser.password}
            >
              Создать
            </Button>
            <Button variant="subtle" onClick={createModal.onClose}>
              Отмена
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      <Modal isOpen={editModal.isOpen} onClose={editModal.onClose}>
        <ModalOverlay />
        <ModalContent borderRadius="md">
          <ModalHeader>Изменить пользователя</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <UserForm
              value={editForm}
              departments={departmentsData?.data ?? []}
              projects={projectsData?.data ?? []}
              onChange={setEditForm}
              isEdit
            />
          </ModalBody>
          <ModalFooter gap={3}>
            <Button
              onClick={() => {
                if (!editingUser) return
                updateMutation.mutate({
                  userId: editingUser.id,
                  payload: {
                    email: editForm.email,
                    full_name: editForm.full_name || null,
                    password: editForm.password || null,
                    is_active: editForm.is_active,
                    is_superuser: editForm.is_superuser,
                    must_change_password: editForm.must_change_password,
                    system_role: editForm.system_role,
                    department_id: editForm.department_id
                      ? Number(editForm.department_id)
                      : null,
                  },
                })
              }}
              isLoading={updateMutation.isPending}
              isDisabled={!editForm.email}
            >
              Сохранить
            </Button>
            <Button variant="subtle" onClick={editModal.onClose}>
              Отмена
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      <Modal
        isOpen={accessMapModal.isOpen}
        onClose={() => {
          accessMapModal.onClose()
          setAccessMapUser(null)
          setAccessOrgId("")
          setAccessGroupId("")
          setAccessGroupRole("member")
        }}
        size="6xl"
      >
        <ModalOverlay />
        <ModalContent borderRadius="md">
          <ModalHeader>
            Карта доступов пользователя
            {accessMapUser ? `: ${accessMapUser.full_name || accessMapUser.email}` : ""}
          </ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            {accessMapLoading && <Text>Загрузка доступа...</Text>}
            {!accessMapLoading && !accessMapData && (
              <Text color="gray.600">Не удалось загрузить карту доступов.</Text>
            )}
            {accessMapData && (
              <VStack align="stretch" spacing={4}>
                <Box
                  borderWidth="1px"
                  borderColor="ui.border"
                  borderRadius="md"
                  p={3}
                  bg="gray.50"
                >
                  <HStack justify="space-between" flexWrap="wrap">
                    <HStack spacing={2} flexWrap="wrap">
                      <Badge colorScheme="purple" borderRadius="sm">
                        {ROLE_META[normalizeSystemRole(accessMapData.system_role)].label}
                      </Badge>
                      <Badge colorScheme={accessMapData.is_superuser ? "red" : "gray"} borderRadius="sm">
                        {accessMapData.is_superuser ? "Superuser" : "Обычный режим"}
                      </Badge>
                      <Badge colorScheme="blue" borderRadius="sm">
                        Группы: {accessMapData.user_group_ids.length}
                      </Badge>
                      <Badge colorScheme="orange" borderRadius="sm">
                        Доступных проектов: {accessMapData.accessible_projects.length}
                      </Badge>
                    </HStack>
                    <Text fontSize="sm" color="gray.600">
                      Primary группа: {accessMapData.primary_group_name || "-"}
                    </Text>
                  </HStack>
                  {(accessMapData.managed_group_ids.length > 0 ||
                    accessMapData.managed_organization_ids.length > 0) && (
                    <HStack spacing={2} mt={2} flexWrap="wrap">
                      {accessMapData.managed_group_ids.length > 0 && (
                        <Badge borderRadius="sm" colorScheme="teal">
                          Управляемые группы: {accessMapData.managed_group_ids.join(", ")}
                        </Badge>
                      )}
                      {accessMapData.managed_organization_ids.length > 0 && (
                        <Badge borderRadius="sm" colorScheme="pink">
                          Управляемые организации:{" "}
                          {accessMapData.managed_organization_ids.join(", ")}
                        </Badge>
                      )}
                    </HStack>
                  )}
                  {accessMapData.notes.length > 0 && (
                    <List spacing={1} mt={2}>
                      {accessMapData.notes.map((note) => (
                        <ListItem key={note} fontSize="sm" color="gray.700">
                          • {note}
                        </ListItem>
                      ))}
                    </List>
                  )}
                </Box>

                <Grid templateColumns={{ base: "1fr", md: "1fr 1fr" }} gap={4}>
                  <Box borderWidth="1px" borderColor="ui.border" borderRadius="md" p={3}>
                    <Text fontWeight="700" mb={2}>
                      Организации и роли
                    </Text>
                    <Box maxH="220px" overflowY="auto">
                      <Table size="sm">
                        <Thead>
                          <Tr>
                            <Th>Организация</Th>
                            <Th>Роль</Th>
                            <Th>Статус</Th>
                          </Tr>
                        </Thead>
                        <Tbody>
                          {accessMapData.organizations.length === 0 && (
                            <Tr>
                              <Td colSpan={3}>Нет записей</Td>
                            </Tr>
                          )}
                          {accessMapData.organizations.map((row) => (
                            <Tr key={`${row.organization_id}-${row.role_name}-${row.is_active}`}>
                              <Td>{row.organization_name || `#${row.organization_id}`}</Td>
                              <Td>{groupRoleLabel(row.role_name)}</Td>
                              <Td>
                                <Badge colorScheme={row.is_active ? "green" : "gray"} borderRadius="sm">
                                  {row.is_active ? "Активен" : "Неактивен"}
                                </Badge>
                              </Td>
                            </Tr>
                          ))}
                        </Tbody>
                      </Table>
                    </Box>
                  </Box>

                  <Box borderWidth="1px" borderColor="ui.border" borderRadius="md" p={3}>
                    <Text fontWeight="700" mb={2}>
                      Группы и роли
                    </Text>
                    <HStack spacing={2} mb={3} align="end" flexWrap="wrap">
                      <FormControl maxW="220px">
                        <FormLabel mb={1} fontSize="xs">
                          Организация
                        </FormLabel>
                        <Select
                          size="sm"
                          value={accessOrgId}
                          onChange={(event) => setAccessOrgId(event.target.value)}
                        >
                          <option value="">Выберите организацию</option>
                          {(organizationsForAccess?.data ?? []).map((org) => (
                            <option key={org.id} value={org.id}>
                              {org.name}
                            </option>
                          ))}
                        </Select>
                      </FormControl>
                      <FormControl maxW="260px" isDisabled={!accessOrgId}>
                        <FormLabel mb={1} fontSize="xs">
                          Группа
                        </FormLabel>
                        <Select
                          size="sm"
                          value={accessGroupId}
                          onChange={(event) => setAccessGroupId(event.target.value)}
                        >
                          <option value="">Выберите группу</option>
                          {(groupsForAccess?.data ?? []).map((group) => (
                            <option key={group.id} value={group.id}>
                              {group.name}
                            </option>
                          ))}
                        </Select>
                      </FormControl>
                      <FormControl maxW="160px">
                        <FormLabel mb={1} fontSize="xs">
                          Роль
                        </FormLabel>
                        <Select
                          size="sm"
                          value={accessGroupRole}
                          onChange={(event) =>
                            setAccessGroupRole(
                              event.target.value as "owner" | "manager" | "member",
                            )
                          }
                        >
                          <option value="member">Участник</option>
                          <option value="manager">Руководитель</option>
                          <option value="owner">Директор</option>
                        </Select>
                      </FormControl>
                      <Button
                        size="sm"
                        onClick={() => {
                          if (!accessMapUser?.id || !accessGroupId) return
                          addGroupMembershipMutation.mutate({
                            groupId: Number(accessGroupId),
                            userId: accessMapUser.id,
                            roleName: accessGroupRole,
                          })
                        }}
                        isDisabled={!accessMapUser?.id || !accessGroupId}
                        isLoading={addGroupMembershipMutation.isPending}
                      >
                        Добавить в группу
                      </Button>
                    </HStack>
                    <Box maxH="220px" overflowY="auto">
                      <Table size="sm">
                        <Thead>
                          <Tr>
                            <Th>Группа</Th>
                            <Th>Организация</Th>
                            <Th>Роль</Th>
                            <Th>Статус</Th>
                            <Th>Действия</Th>
                          </Tr>
                        </Thead>
                        <Tbody>
                          {accessMapData.groups.length === 0 && (
                            <Tr>
                              <Td colSpan={5}>Нет записей</Td>
                            </Tr>
                          )}
                          {accessMapData.groups.map((row) => (
                            <Tr key={`${row.group_id}-${row.role_name}-${row.is_primary}-${row.is_active}`}>
                              <Td>
                                {row.group_name || `#${row.group_id}`}
                                {row.is_primary && (
                                  <Badge ml={2} colorScheme="blue" borderRadius="sm">
                                    Primary
                                  </Badge>
                                )}
                              </Td>
                              <Td>{row.organization_name || "-"}</Td>
                              <Td>{groupRoleLabel(row.role_name)}</Td>
                              <Td>
                                <Badge colorScheme={row.is_active ? "green" : "gray"} borderRadius="sm">
                                  {row.is_active ? "Активен" : "Неактивен"}
                                </Badge>
                              </Td>
                              <Td>
                                {row.is_direct_membership ? (
                                  <HStack spacing={1}>
                                    <Button
                                      size="xs"
                                      variant="outline"
                                      onClick={() => {
                                        if (!accessMapUser?.id) return
                                        updateGroupMembershipMutation.mutate({
                                          groupId: row.group_id,
                                          userId: accessMapUser.id,
                                          patch: { is_active: !row.is_active },
                                        })
                                      }}
                                      isLoading={
                                        updateGroupMembershipMutation.isPending &&
                                        updateGroupMembershipMutation.variables?.groupId === row.group_id
                                      }
                                    >
                                      {row.is_active ? "Отключить" : "Включить"}
                                    </Button>
                                    <Button
                                      size="xs"
                                      variant="outline"
                                      colorScheme="red"
                                      onClick={() => {
                                        if (!accessMapUser?.id) return
                                        removeGroupMembershipMutation.mutate({
                                          groupId: row.group_id,
                                          userId: accessMapUser.id,
                                        })
                                      }}
                                      isLoading={
                                        removeGroupMembershipMutation.isPending &&
                                        removeGroupMembershipMutation.variables?.groupId === row.group_id
                                      }
                                    >
                                      Удалить
                                    </Button>
                                  </HStack>
                                ) : (
                                  <Text fontSize="xs" color="gray.500">
                                    Эффективный доступ
                                  </Text>
                                )}
                              </Td>
                            </Tr>
                          ))}
                        </Tbody>
                      </Table>
                    </Box>
                  </Box>
                </Grid>

                <Divider />

                <Box borderWidth="1px" borderColor="ui.border" borderRadius="md" p={3}>
                  <Text fontWeight="700" mb={2}>
                    Проектные назначения ролей (RBAC)
                  </Text>
                  <Box maxH="220px" overflowY="auto">
                    <Table size="sm">
                      <Thead>
                        <Tr>
                          <Th>Проект</Th>
                          <Th>Организация</Th>
                          <Th>Роль</Th>
                          <Th>Тип назначения</Th>
                          <Th>Субъект</Th>
                          <Th>Статус</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {accessMapData.project_role_assignments.length === 0 && (
                          <Tr>
                            <Td colSpan={6}>Нет RBAC-назначений</Td>
                          </Tr>
                        )}
                        {accessMapData.project_role_assignments.map((row) => (
                          <Tr
                            key={`${row.project_id}-${row.subject_type}-${row.subject_group_id ?? row.subject_user_id}-${row.role_key}-${row.is_active}`}
                          >
                            <Td>{row.project_name || `#${row.project_id}`}</Td>
                            <Td>{row.organization_name || "-"}</Td>
                            <Td>{row.role_title || row.role_key}</Td>
                            <Td>{row.subject_type === "group" ? "Группа" : "Пользователь"}</Td>
                            <Td>
                              {row.subject_type === "group"
                                ? row.subject_group_name || `#${row.subject_group_id}`
                                : accessMapData.email}
                            </Td>
                            <Td>
                              <Badge colorScheme={row.is_active ? "green" : "gray"} borderRadius="sm">
                                {row.is_active ? "Активно" : "Неактивно"}
                              </Badge>
                            </Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  </Box>
                </Box>

                <Box borderWidth="1px" borderColor="ui.border" borderRadius="md" p={3}>
                  <Text fontWeight="700" mb={2}>
                    Legacy-участие в проектах (project_member)
                  </Text>
                  <Box maxH="220px" overflowY="auto">
                    <Table size="sm">
                      <Thead>
                        <Tr>
                          <Th>Проект</Th>
                          <Th>Организация</Th>
                          <Th>Роль</Th>
                          <Th>Статус</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {accessMapData.project_memberships.length === 0 && (
                          <Tr>
                            <Td colSpan={4}>Нет legacy-участий</Td>
                          </Tr>
                        )}
                        {accessMapData.project_memberships.map((row) => (
                          <Tr key={`${row.project_id}-${row.role}-${row.is_active}`}>
                            <Td>{row.project_name || `#${row.project_id}`}</Td>
                            <Td>{row.organization_name || "-"}</Td>
                            <Td>{projectMemberRoleLabel(row.role)}</Td>
                            <Td>
                              <Badge colorScheme={row.is_active ? "green" : "gray"} borderRadius="sm">
                                {row.is_active ? "Активно" : "Неактивно"}
                              </Badge>
                            </Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  </Box>
                </Box>

                <Box borderWidth="1px" borderColor="ui.border" borderRadius="md" p={3}>
                  <Text fontWeight="700" mb={2}>
                    Итог: видимые проекты и причины
                  </Text>
                  <Box maxH="320px" overflowY="auto">
                    <Table size="sm">
                      <Thead>
                        <Tr>
                          <Th>Проект</Th>
                          <Th>Организация</Th>
                          <Th>Причины видимости</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {accessMapData.accessible_projects.length === 0 && (
                          <Tr>
                            <Td colSpan={3}>Проекты недоступны</Td>
                          </Tr>
                        )}
                        {accessMapData.accessible_projects.map((row) => (
                          <Tr key={row.project_id}>
                            <Td>{row.project_name}</Td>
                            <Td>{row.organization_name || "-"}</Td>
                            <Td>
                              <VStack align="start" spacing={1}>
                                {row.reasons.map((reason) => (
                                  <Badge key={`${row.project_id}-${reason}`} borderRadius="sm" colorScheme="blue">
                                    {reason}
                                  </Badge>
                                ))}
                              </VStack>
                            </Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  </Box>
                </Box>
              </VStack>
            )}
          </ModalBody>
          <ModalFooter>
            <HStack justify="space-between" w="full">
              <Text fontSize="sm" color="gray.500">
                {accessMapFetching ? "Обновление данных..." : "Проверка причин доступа доступна по каждому проекту"}
              </Text>
              <Button
                variant="subtle"
                onClick={() => {
                  accessMapModal.onClose()
                  setAccessMapUser(null)
                  setAccessOrgId("")
                  setAccessGroupId("")
                  setAccessGroupRole("member")
                }}
              >
                Закрыть
              </Button>
            </HStack>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Container>
  )
}

function UserForm({
  value,
  departments,
  projects,
  onChange,
  isEdit,
}: {
  value: UserFormState
  departments: Array<{ id: number; name: string }>
  projects: Array<{ id: number; name: string }>
  onChange: (next: UserFormState) => void
  isEdit: boolean
}) {
  return (
    <Grid templateColumns={{ base: "1fr", md: "1fr 1fr" }} gap={3}>
      <GridItem colSpan={{ base: 1, md: 2 }}>
        <FormControl isRequired>
          <FormLabel>Email</FormLabel>
          <Input
            value={value.email}
            onChange={(e) => onChange({ ...value, email: e.target.value })}
            type="email"
          />
        </FormControl>
      </GridItem>
      <GridItem colSpan={{ base: 1, md: 2 }}>
        <FormControl>
          <FormLabel>ФИО</FormLabel>
          <Input
            value={value.full_name}
            onChange={(e) => onChange({ ...value, full_name: e.target.value })}
          />
        </FormControl>
      </GridItem>
      <GridItem colSpan={{ base: 1, md: 2 }}>
        <FormControl isRequired={!isEdit}>
          <FormLabel>
            {isEdit ? "Новый пароль (опционально)" : "Пароль"}
          </FormLabel>
          <Input
            type="password"
            value={value.password}
            onChange={(e) => onChange({ ...value, password: e.target.value })}
          />
        </FormControl>
      </GridItem>
      <GridItem>
        <FormControl>
          <FormLabel>Системная роль</FormLabel>
          <Select
            value={value.system_role}
            onChange={(e) =>
              onChange({
                ...value,
                system_role: e.target.value as UserFormState["system_role"],
              })
            }
          >
            <option value="user">Пользователь</option>
            <option value="system_admin">Системный администратор</option>
          </Select>
          <Text mt={1} fontSize="xs" color="ui.muted">
            {ROLE_META[value.system_role].hint}
          </Text>
        </FormControl>
      </GridItem>
      <GridItem>
        <FormControl>
          <FormLabel>Департамент</FormLabel>
          <Select
            value={value.department_id}
            onChange={(e) =>
              onChange({ ...value, department_id: e.target.value })
            }
          >
            <option value="">Не задан</option>
            {departments.map((department) => (
              <option key={department.id} value={department.id}>
                {department.name}
              </option>
            ))}
          </Select>
        </FormControl>
      </GridItem>
      <GridItem>
        <FormControl display="flex" justifyContent="space-between" mt={2}>
          <FormLabel m={0}>Активен</FormLabel>
          <Switch
            isChecked={value.is_active}
            onChange={(e) =>
              onChange({ ...value, is_active: e.target.checked })
            }
          />
        </FormControl>
      </GridItem>
      <GridItem>
        <FormControl display="flex" justifyContent="space-between" mt={2}>
          <FormLabel m={0}>Superuser (полный системный доступ)</FormLabel>
          <Switch
            isChecked={value.is_superuser}
            onChange={(e) =>
              onChange({ ...value, is_superuser: e.target.checked })
            }
          />
        </FormControl>
      </GridItem>
      <GridItem colSpan={{ base: 1, md: 2 }}>
        <FormControl display="flex" justifyContent="space-between" mt={2}>
          <FormLabel m={0}>
            Обязательно сменить пароль при следующем входе
          </FormLabel>
          <Switch
            isChecked={value.must_change_password}
            onChange={(e) =>
              onChange({ ...value, must_change_password: e.target.checked })
            }
          />
        </FormControl>
      </GridItem>
      {!isEdit && (
        <>
          <GridItem colSpan={{ base: 1, md: 2 }}>
            <FormControl>
              <FormLabel>Привязка к проекту (опционально)</FormLabel>
              <Select
                value={value.bind_project_id}
                onChange={(e) =>
                  onChange({ ...value, bind_project_id: e.target.value })
                }
              >
                <option value="">Без привязки</option>
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                  </option>
                ))}
              </Select>
            </FormControl>
          </GridItem>
          <GridItem colSpan={{ base: 1, md: 2 }}>
            <FormControl isDisabled={!value.bind_project_id}>
              <FormLabel>Роль в проекте</FormLabel>
              <Select
                value={value.bind_project_role}
                onChange={(e) =>
                  onChange({
                    ...value,
                    bind_project_role: e.target
                      .value as UserFormState["bind_project_role"],
                  })
                }
              >
                <option value="reader">Reader</option>
                <option value="contributor">Contributor</option>
                <option value="project_admin">Project Admin</option>
              </Select>
            </FormControl>
          </GridItem>
        </>
      )}
    </Grid>
  )
}
