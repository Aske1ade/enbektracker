import {
  Avatar,
  Badge,
  Box,
  Button,
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
  GridItem,
  HStack,
  Heading,
  Input,
  NumberInput,
  NumberInputField,
  Select,
  Spinner,
  Switch,
  Table,
  Tab,
  TabList,
  TabPanel,
  TabPanels,
  Tabs,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tr,
  VStack,
  useColorModeValue,
  useDisclosure,
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useEffect, useMemo, useRef, useState } from "react"
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import type { UserPublic } from "../../client"
import useCustomToast from "../../hooks/useCustomToast"
import { trackerApi } from "../../services/trackerApi"
import type {
  CalendarDayTask,
  CalendarViewBucket,
  ProjectMember,
} from "../../types/tracker"
import {
  DEFAULT_PROJECT_ICON_PATH,
  fallbackAccentBySeed,
  readProjectAccent,
  resolveProjectIconPath,
  writeProjectAccent,
} from "../../utils/projectVisuals"

export const Route = createFileRoute("/_layout/projects/$projectId")({
  component: ProjectDetailPage,
})

type AccessRoleKey = "reader" | "contributor" | "project_admin"
type MemberRoleKey = ProjectMember["role"]

type ProjectMemberDraft = {
  user_id: number
  user_name: string
  user_email: string
  role: MemberRoleKey
  is_active: boolean
  is_removed: boolean
}

type AccessUserDraft = {
  user_id: number
  user_name: string
  user_email: string
  role_key: AccessRoleKey
  is_active: boolean
}

type AccessGroupDraft = {
  group_id: number
  group_name: string
  organization_name: string
  role_key: AccessRoleKey
  is_active: boolean
}

type AvailableGroup = {
  id: number
  name: string
  organization_id: number
  organization_name: string
}

function ProjectDetailPage() {
  const { projectId } = Route.useParams()
  const projectNumber = Number(projectId)
  const queryClient = useQueryClient()
  const currentUser = queryClient.getQueryData<UserPublic & { system_role?: string }>([
    "currentUser",
  ])
  const showToast = useCustomToast()
  const dayDrawer = useDisclosure()
  const pageCardBg = useColorModeValue("white", "#162235")
  const pageCardAltBg = useColorModeValue("white", "#142033")
  const drawerBg = useColorModeValue("white", "#101b2f")
  const drawerHeaderBg = useColorModeValue("white", "#15263f")
  const drawerTextColor = useColorModeValue("ui.text", "ui.light")
  const dayTabInactiveBg = useColorModeValue("rgba(234,240,248,0.9)", "#1A2B44")
  const dayTabInactiveColor = useColorModeValue("ui.main", "ui.light")
  const dayTabInactiveHoverBg = useColorModeValue("#dbe7f6", "#233a5d")

  const [showMembersCompact, setShowMembersCompact] = useState(false)

  const { data: project, isLoading: projectLoading } = useQuery({
    queryKey: ["project", projectNumber],
    queryFn: () => trackerApi.getProject(projectNumber),
  })

  const { data: membersData, isLoading: membersLoading } = useQuery({
    queryKey: ["project-members", projectNumber],
    queryFn: () => trackerApi.listProjectMembers(projectNumber),
  })

  const canManageAccess = useMemo(() => {
    if (
      currentUser?.is_superuser ||
      currentUser?.system_role === "system_admin" ||
      currentUser?.system_role === "admin"
    ) {
      return true
    }
    const myMembership = (membersData?.data ?? []).find(
      (member) =>
        member.user_id === currentUser?.id && member.is_active && member.role === "manager",
    )
    return Boolean(myMembership)
  }, [currentUser, membersData?.data])

  const { data: allUsersData } = useQuery({
    queryKey: ["all-users-for-project-access"],
    queryFn: () => trackerApi.listUsers(),
    retry: false,
  })

  const { data: allGroupsData } = useQuery({
    queryKey: ["all-groups-for-project-access"],
    queryFn: async (): Promise<AvailableGroup[]> => {
      const organizations = await trackerApi.listOrganizations()
      const byOrg = await Promise.all(
        organizations.data.map(async (organization) => {
          const groups = await trackerApi.getOrganizationGroups(organization.id)
          return groups.data.map((group) => ({
            id: group.id,
            name: group.name,
            organization_id: organization.id,
            organization_name: organization.name,
          }))
        }),
      )
      return byOrg.flat()
    },
    retry: false,
  })

  const { data: accessUsersData, isLoading: accessUsersLoading } = useQuery({
    queryKey: ["project-access-users", projectNumber],
    queryFn: () => trackerApi.getProjectAccessUsers(projectNumber),
  })

  const { data: accessGroupsData, isLoading: accessGroupsLoading } = useQuery({
    queryKey: ["project-access-groups", projectNumber],
    queryFn: () => trackerApi.getProjectAccessGroups(projectNumber),
  })

  const [policyForm, setPolicyForm] = useState({
    name: "",
    icon: DEFAULT_PROJECT_ICON_PATH,
    description: "",
    require_close_comment: false,
    require_close_attachment: false,
    deadline_yellow_days: 3,
    deadline_normal_days: 5,
  })
  const [projectAccentColor, setProjectAccentColor] = useState("#1D4ED8")
  const projectIconInputRef = useRef<HTMLInputElement | null>(null)

  const [projectMembersDraft, setProjectMembersDraft] = useState<ProjectMemberDraft[]>([])
  const [newMemberUserId, setNewMemberUserId] = useState("")
  const [newMemberRole, setNewMemberRole] = useState<MemberRoleKey>("executor")

  const [accessUsersDraft, setAccessUsersDraft] = useState<AccessUserDraft[]>([])
  const [newAccessUserId, setNewAccessUserId] = useState("")
  const [newAccessUserRole, setNewAccessUserRole] = useState<AccessRoleKey>("contributor")

  const [accessGroupsDraft, setAccessGroupsDraft] = useState<AccessGroupDraft[]>([])
  const [newAccessGroupId, setNewAccessGroupId] = useState("")
  const [newAccessGroupRole, setNewAccessGroupRole] = useState<AccessRoleKey>("reader")

  const [calendarMode, setCalendarMode] = useState<"day" | "week" | "month">("month")
  const [calendarDate, setCalendarDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [selectedDay, setSelectedDay] = useState<string | null>(null)

  const { data: projectCalendar, isLoading: projectCalendarLoading } = useQuery({
    queryKey: ["project-wall-calendar", projectNumber, calendarMode, calendarDate],
    queryFn: () =>
      trackerApi.calendarView({
        date: calendarDate,
        mode: calendarMode,
        scope: "project",
        project_id: projectNumber,
      }),
  })

  useEffect(() => {
    if (!project) return
    const fallbackAccent = fallbackAccentBySeed(
      project.department_name || project.block_name || project.organization_name || project.name,
    )
    setProjectAccentColor(readProjectAccent(project.id) || fallbackAccent)
    setPolicyForm({
      name: project.name,
      icon: resolveProjectIconPath(project.icon),
      description: project.description || "",
      require_close_comment: project.require_close_comment,
      require_close_attachment: project.require_close_attachment,
      deadline_yellow_days: project.deadline_yellow_days,
      deadline_normal_days: project.deadline_normal_days,
    })
  }, [project])

  useEffect(() => {
    const rows = membersData?.data ?? []
    setProjectMembersDraft(
      rows.map((member) => ({
        user_id: member.user_id,
        user_name: member.user_name || `Пользователь #${member.user_id}`,
        user_email: member.user_email || "-",
        role: member.role,
        is_active: member.is_active,
        is_removed: false,
      })),
    )
  }, [membersData?.data])

  useEffect(() => {
    const rows = accessUsersData?.data ?? []
    setAccessUsersDraft(
      rows.map((row) => ({
        user_id: row.user_id,
        user_name: row.user_name || `Пользователь #${row.user_id}`,
        user_email: row.user_email || "-",
        role_key: row.role_key,
        is_active: row.is_active,
      })),
    )
  }, [accessUsersData?.data])

  useEffect(() => {
    const groupsById = new Map((allGroupsData ?? []).map((group) => [group.id, group]))
    const rows = accessGroupsData?.data ?? []
    setAccessGroupsDraft(
      rows.map((row) => ({
        group_id: row.group_id,
        group_name: row.group_name || `Группа #${row.group_id}`,
        organization_name:
          groupsById.get(row.group_id)?.organization_name ||
          (row.organization_id ? `Организация #${row.organization_id}` : "-"),
        role_key: row.role_key,
        is_active: row.is_active,
      })),
    )
  }, [accessGroupsData?.data, allGroupsData])

  const updateProjectMutation = useMutation({
    mutationFn: () =>
      trackerApi.updateProject(projectNumber, {
        name: policyForm.name,
        icon: (policyForm.icon || "").trim() || null,
        description: policyForm.description || null,
        require_close_comment: policyForm.require_close_comment,
        require_close_attachment: policyForm.require_close_attachment,
        deadline_yellow_days: policyForm.deadline_yellow_days,
        deadline_normal_days: policyForm.deadline_normal_days,
      }),
    onSuccess: () => {
      showToast.success("Успешно", "Настройки проекта обновлены")
      queryClient.invalidateQueries({ queryKey: ["project", projectNumber] })
      queryClient.invalidateQueries({ queryKey: ["projects"] })
    },
    onError: (error) => showToast.error("Не удалось обновить настройки проекта", error),
  })

  const uploadProjectIconMutation = useMutation({
    mutationFn: (file: File) => trackerApi.uploadProjectIcon(projectNumber, file),
    onSuccess: (updatedProject) => {
      setPolicyForm((prev) => ({
        ...prev,
        icon: resolveProjectIconPath(updatedProject.icon),
      }))
      queryClient.invalidateQueries({ queryKey: ["project", projectNumber] })
      queryClient.invalidateQueries({ queryKey: ["projects"] })
      showToast.success("Успешно", "Иконка проекта обновлена")
    },
    onError: (error) => showToast.error("Не удалось загрузить иконку проекта", error),
  })

  const handleSaveProjectSettings = () => {
    writeProjectAccent(projectNumber, projectAccentColor)
    updateProjectMutation.mutate()
  }

  const handleProjectIconPick = (file?: File) => {
    if (!file) return
    uploadProjectIconMutation.mutate(file)
  }

  const saveProjectMembersMutation = useMutation({
    mutationFn: async () => {
      const existingByUserId = new Map((membersData?.data ?? []).map((row) => [row.user_id, row]))

      for (const draftRow of projectMembersDraft) {
        const existing = existingByUserId.get(draftRow.user_id)

        if (draftRow.is_removed) {
          if (existing) {
            await trackerApi.deleteProjectMember(projectNumber, draftRow.user_id)
          }
          continue
        }

        if (!existing) {
          await trackerApi.createProjectMember(projectNumber, {
            user_id: draftRow.user_id,
            role: draftRow.role,
            is_active: draftRow.is_active,
          })
          continue
        }

        const patch: Partial<{ role: MemberRoleKey; is_active: boolean }> = {}
        if (existing.role !== draftRow.role) {
          patch.role = draftRow.role
        }
        if (existing.is_active !== draftRow.is_active) {
          patch.is_active = draftRow.is_active
        }

        if (Object.keys(patch).length > 0) {
          await trackerApi.updateProjectMember(projectNumber, draftRow.user_id, patch)
        }
      }
    },
    onSuccess: () => {
      showToast.success("Успешно", "Участники проекта обновлены")
      queryClient.invalidateQueries({ queryKey: ["project-members", projectNumber] })
      queryClient.invalidateQueries({ queryKey: ["projects"] })
      queryClient.invalidateQueries({ queryKey: ["project-wall-calendar", projectNumber] })
    },
    onError: (error) => showToast.error("Не удалось обновить участников проекта", error),
  })

  const saveAccessUsersMutation = useMutation({
    mutationFn: () =>
      trackerApi.replaceProjectAccessUsers(
        projectNumber,
        accessUsersDraft.map((row) => ({
          user_id: row.user_id,
          role_key: row.role_key,
          is_active: row.is_active,
        })),
      ),
    onSuccess: () => {
      showToast.success("Успешно", "Права пользователей обновлены")
      queryClient.invalidateQueries({ queryKey: ["project-access-users", projectNumber] })
      queryClient.invalidateQueries({ queryKey: ["projects"] })
    },
    onError: (error) => showToast.error("Не удалось обновить права пользователей", error),
  })

  const saveAccessGroupsMutation = useMutation({
    mutationFn: () =>
      trackerApi.replaceProjectAccessGroups(
        projectNumber,
        accessGroupsDraft.map((row) => ({
          group_id: row.group_id,
          role_key: row.role_key,
          is_active: row.is_active,
        })),
      ),
    onSuccess: () => {
      showToast.success("Успешно", "Права групп обновлены")
      queryClient.invalidateQueries({ queryKey: ["project-access-groups", projectNumber] })
      queryClient.invalidateQueries({ queryKey: ["projects"] })
    },
    onError: (error) => showToast.error("Не удалось обновить права групп", error),
  })

  const availableMemberOptions = useMemo(() => {
    const selected = new Set(
      projectMembersDraft.filter((row) => !row.is_removed).map((row) => row.user_id),
    )
    return (allUsersData?.data ?? [])
      .filter((user) => !selected.has(user.id))
      .map((user) => ({
        id: user.id,
        label: user.full_name || user.email,
        email: user.email,
      }))
      .sort((a, b) => a.label.localeCompare(b.label, "ru"))
  }, [allUsersData?.data, projectMembersDraft])

  const availableUserOptions = useMemo(() => {
    const selected = new Set(accessUsersDraft.map((row) => row.user_id))
    return (allUsersData?.data ?? [])
      .filter((user) => !selected.has(user.id))
      .map((user) => ({
        id: user.id,
        label: user.full_name || user.email,
        email: user.email,
      }))
      .sort((a, b) => a.label.localeCompare(b.label, "ru"))
  }, [accessUsersDraft, allUsersData?.data])

  const availableGroupOptions = useMemo(() => {
    const selected = new Set(accessGroupsDraft.map((row) => row.group_id))
    return (allGroupsData ?? [])
      .filter((group) => !selected.has(group.id))
      .sort((a, b) => a.name.localeCompare(b.name, "ru"))
  }, [accessGroupsDraft, allGroupsData])

  const addProjectMember = () => {
    const userId = Number(newMemberUserId)
    if (!userId) return
    const user = availableMemberOptions.find((item) => item.id === userId)
    if (!user) return
    setProjectMembersDraft((prev) => [
      ...prev,
      {
        user_id: user.id,
        user_name: user.label,
        user_email: user.email,
        role: newMemberRole,
        is_active: true,
        is_removed: false,
      },
    ])
    setNewMemberUserId("")
  }

  const addAccessUser = () => {
    const userId = Number(newAccessUserId)
    if (!userId) return
    const user = availableUserOptions.find((item) => item.id === userId)
    if (!user) return
    setAccessUsersDraft((prev) => [
      ...prev,
      {
        user_id: user.id,
        user_name: user.label,
        user_email: user.email,
        role_key: newAccessUserRole,
        is_active: true,
      },
    ])
    setNewAccessUserId("")
  }

  const addAccessGroup = () => {
    const groupId = Number(newAccessGroupId)
    if (!groupId) return
    const group = availableGroupOptions.find((item) => item.id === groupId)
    if (!group) return
    setAccessGroupsDraft((prev) => [
      ...prev,
      {
        group_id: group.id,
        group_name: group.name,
        organization_name: group.organization_name,
        role_key: newAccessGroupRole,
        is_active: true,
      },
    ])
    setNewAccessGroupId("")
  }

  const visibleMembers = useMemo(
    () => projectMembersDraft.filter((item) => !item.is_removed),
    [projectMembersDraft],
  )

  const compactMembers = useMemo(() => visibleMembers.slice(0, 12), [visibleMembers])

  const membersSummary = useMemo(() => {
    const active = visibleMembers.filter((member) => member.is_active)
    const controllers = active.filter((member) => member.role === "controller").length
    const managers = active.filter((member) => member.role === "manager").length
    return {
      total: visibleMembers.length,
      active: active.length,
      controllers,
      managers,
    }
  }, [visibleMembers])

  const bucketsByDay = useMemo(() => {
    const map = new Map<string, CalendarViewBucket>()
    for (const bucket of projectCalendar?.data ?? []) {
      map.set(String(bucket.day).slice(0, 10), bucket)
    }
    return map
  }, [projectCalendar?.data])

  const selectedBucket = selectedDay ? bucketsByDay.get(selectedDay) : undefined
  const dayTabs = useMemo(
    () =>
      (projectCalendar?.data ?? [])
        .map((bucket) => String(bucket.day).slice(0, 10))
        .sort((a, b) => a.localeCompare(b)),
    [projectCalendar?.data],
  )

  const calendarTotals = useMemo(() => {
    const buckets = projectCalendar?.data ?? []
    let total = 0
    let overdue = 0
    let closed = 0
    for (const bucket of buckets) {
      total += bucket.total_count
      overdue += bucket.overdue_count
      closed += bucket.closed_count
    }
    return { total, overdue, closed, active: Math.max(0, total - closed) }
  }, [projectCalendar?.data])

  const participantLoad = useMemo(() => {
    const counts = new Map<string, number>()
    for (const bucket of projectCalendar?.data ?? []) {
      for (const task of bucket.tasks) {
        if (task.closed_at) continue
        const name = task.assignee_name || "Не назначен"
        counts.set(name, (counts.get(name) ?? 0) + 1)
      }
    }
    return [...counts.entries()]
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 12)
  }, [projectCalendar?.data])

  const anchorDate = useMemo(() => new Date(`${calendarDate}T00:00:00`), [calendarDate])
  const monthStart = useMemo(
    () => new Date(anchorDate.getFullYear(), anchorDate.getMonth(), 1),
    [anchorDate],
  )
  const monthEnd = useMemo(
    () => new Date(anchorDate.getFullYear(), anchorDate.getMonth() + 1, 0),
    [anchorDate],
  )
  const gridStart = useMemo(() => startOfWeekMonday(monthStart), [monthStart])
  const gridEnd = useMemo(() => endOfWeekSunday(monthEnd), [monthEnd])
  const gridDays = useMemo(() => {
    const days: Date[] = []
    const current = new Date(gridStart)
    while (current <= gridEnd) {
      days.push(new Date(current))
      current.setDate(current.getDate() + 1)
    }
    return days
  }, [gridStart, gridEnd])

  const calendarHeaderLabel = useMemo(() => {
    if (calendarMode === "day") {
      return anchorDate.toLocaleDateString("ru-RU", {
        day: "2-digit",
        month: "long",
        year: "numeric",
      })
    }
    if (calendarMode === "week") {
      const from = projectCalendar?.date_from
      const to = projectCalendar?.date_to
      if (!from || !to) return "Неделя"
      return `${new Date(from).toLocaleDateString("ru-RU")} - ${new Date(to).toLocaleDateString(
        "ru-RU",
      )}`
    }
    return capitalize(
      anchorDate.toLocaleDateString("ru-RU", {
        month: "long",
        year: "numeric",
      }),
    )
  }, [anchorDate, calendarMode, projectCalendar?.date_from, projectCalendar?.date_to])

  return (
    <Container maxW="full" py={6}>
      <Box
        mb={5}
        borderWidth="1px"
        borderColor="#154A77"
        borderRadius="16px"
        px={{ base: 4, md: 6 }}
        py={{ base: 4, md: 5 }}
        bg="linear-gradient(120deg, #12385C 0%, #1D5D91 100%)"
        color="white"
        boxShadow="lg"
      >
        <HStack justify="space-between" align="start" flexWrap="wrap" gap={4}>
          <Box>
            <Text fontSize="xs" textTransform="uppercase" letterSpacing="0.08em" color="whiteAlpha.800">
              Проектная стена
            </Text>
            <HStack spacing={3} mt={1}>
              <Box
                w="36px"
                h="36px"
                borderRadius="10px"
                bg="whiteAlpha.220"
                borderWidth="1px"
                borderColor="whiteAlpha.400"
                display="flex"
                alignItems="center"
                justifyContent="center"
                overflow="hidden"
              >
                <Box
                  as="img"
                  src={resolveProjectIconPath(project?.icon)}
                  alt={project?.name || "Project icon"}
                  w="22px"
                  h="22px"
                  objectFit="contain"
                />
              </Box>
              <Heading size="lg">{project?.name || `Проект #${projectId}`}</Heading>
            </HStack>
            <Text mt={2} color="whiteAlpha.900" maxW="820px">
              {project?.description || "Описание проекта не заполнено"}
            </Text>
            <HStack mt={3} spacing={2} flexWrap="wrap">
              <Badge borderRadius="full" colorScheme="cyan" fontSize="11px" px={2} py={0.5}>
                {project?.organization_name || "Без организации"}
              </Badge>
              <Badge borderRadius="full" colorScheme="purple" fontSize="11px" px={2} py={0.5}>
                {project?.block_name || "Без группы"}
              </Badge>
            </HStack>
          </Box>
          <Grid templateColumns="repeat(2, minmax(0, 1fr))" gap={2} minW="290px">
            <MetricTile label="Задач в периоде" value={calendarTotals.total} />
            <MetricTile label="Активные" value={calendarTotals.active} />
            <MetricTile label="Просроченные" value={calendarTotals.overdue} />
            <MetricTile label="Закрытые" value={calendarTotals.closed} />
          </Grid>
        </HStack>
      </Box>

      {projectLoading ? (
        <Spinner />
      ) : (
        <Tabs variant="soft-rounded" colorScheme="blue" mb={4}>
          <TabList flexWrap="wrap" gap={2} mb={3}>
            <Tab>Проектная стена</Tab>
            <Tab>Настройки проекта</Tab>
          </TabList>
          <TabPanels>
            <TabPanel px={0}>
              <Grid templateColumns={{ base: "1fr", md: "repeat(4, 1fr)" }} gap={3} mb={4}>
                <StatPanel title="ЗАДАЧ В ПЕРИОДЕ" value={calendarTotals.total} />
                <StatPanel title="АКТИВНЫЕ" value={calendarTotals.active} />
                <StatPanel
                  title="ПРОСРОЧЕННЫЕ"
                  value={calendarTotals.overdue}
                  valueColor="#B42318"
                />
                <StatPanel title="ЗАКРЫТЫЕ" value={calendarTotals.closed} />
              </Grid>
              <Grid templateColumns={{ base: "1fr", xl: "1.35fr 1fr" }} gap={4}>
                <GridItem>
                  <Box
                    borderWidth="1px"
                    borderColor="ui.border"
                    borderRadius="md"
                    p={4}
                    bg={pageCardBg}
                  >
                    <HStack justify="space-between" mb={3} flexWrap="wrap" gap={2}>
                      <Text fontWeight="700">Календарь проекта</Text>
                      <HStack>
                        <Button
                          size="xs"
                          onClick={() =>
                            setCalendarDate((prev) => shiftCalendarDate(prev, calendarMode, -1))
                          }
                        >
                          ←
                        </Button>
                        <Text minW="220px" textAlign="center" fontWeight="700" fontSize="sm">
                          {calendarHeaderLabel}
                        </Text>
                        <Button
                          size="xs"
                          onClick={() =>
                            setCalendarDate((prev) => shiftCalendarDate(prev, calendarMode, 1))
                          }
                        >
                          →
                        </Button>
                        <Select
                          size="sm"
                          value={calendarMode}
                          onChange={(event) =>
                            setCalendarMode(event.target.value as "day" | "week" | "month")
                          }
                          w="120px"
                        >
                          <option value="day">День</option>
                          <option value="week">Неделя</option>
                          <option value="month">Месяц</option>
                        </Select>
                        <Input
                          size="sm"
                          type="date"
                          value={calendarDate}
                          onChange={(event) => setCalendarDate(event.target.value)}
                          w="150px"
                        />
                      </HStack>
                    </HStack>

                    {projectCalendarLoading ? (
                      <Spinner />
                    ) : calendarMode === "month" ? (
                      <Box borderWidth="1px" borderColor="ui.border" borderRadius="md" overflow="hidden">
                        <Grid templateColumns="repeat(7, minmax(0, 1fr))" borderBottomWidth="1px" borderColor="ui.border">
                          {["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"].map((dayName) => (
                            <Box
                              key={dayName}
                              p={2}
                              borderRightWidth="1px"
                              borderColor="ui.border"
                              fontSize="12px"
                              textTransform="uppercase"
                              fontWeight="700"
                              color="ui.muted"
                            >
                              {dayName}
                            </Box>
                          ))}
                        </Grid>
                        <Grid templateColumns="repeat(7, minmax(0, 1fr))">
                          {gridDays.map((day, index) => {
                            const dayKey = toYmd(day)
                            const bucket = bucketsByDay.get(dayKey)
                            const inCurrentMonth = day.getMonth() === anchorDate.getMonth()
                            const preview = bucket?.tasks.slice(0, 4) ?? []
                            const totalCount = bucket?.total_count ?? 0
                            return (
                              <Box
                                key={`${dayKey}-${index}`}
                                minH="148px"
                                borderRightWidth={(index + 1) % 7 === 0 ? "0" : "1px"}
                                borderBottomWidth="1px"
                                borderColor="ui.border"
                                p={2}
                                bg={calendarCellColor(bucket)}
                                opacity={inCurrentMonth ? 1 : 0.42}
                                cursor={totalCount > 0 ? "pointer" : "default"}
                                onClick={() => {
                                  if (!totalCount) return
                                  setSelectedDay(dayKey)
                                  dayDrawer.onOpen()
                                }}
                              >
                                <Text fontSize="sm" fontWeight="700" mb={1}>
                                  {day.getDate()}
                                </Text>
                                {preview.map((task) => (
                                  <Text
                                    key={task.id}
                                    as={task.closed_at ? "s" : undefined}
                                    fontSize="xs"
                                    color={projectTaskColor(task)}
                                    noOfLines={1}
                                  >
                                    {task.title}
                                  </Text>
                                ))}
                                {totalCount > preview.length ? (
                                  <Text
                                    fontSize="xs"
                                    color="ui.muted"
                                    mt={1}
                                    textDecoration="underline"
                                    onClick={(event) => {
                                      event.stopPropagation()
                                      setCalendarDate(dayKey)
                                      setCalendarMode("day")
                                    }}
                                  >
                                    +{totalCount - preview.length} задач
                                  </Text>
                                ) : null}
                              </Box>
                            )
                          })}
                        </Grid>
                      </Box>
                    ) : (
                      <Table size="sm">
                        <Thead>
                          <Tr>
                            <Th>Дата</Th>
                            <Th>Всего</Th>
                            <Th>Проср.</Th>
                            <Th>Закрыто</Th>
                            <Th>Задачи</Th>
                          </Tr>
                        </Thead>
                        <Tbody>
                          {(projectCalendar?.data ?? []).map((bucket) => {
                            const dayKey = String(bucket.day).slice(0, 10)
                            return (
                              <Tr key={dayKey}>
                                <Td>{new Date(dayKey).toLocaleDateString("ru-RU")}</Td>
                                <Td>{bucket.total_count}</Td>
                                <Td>{bucket.overdue_count}</Td>
                                <Td>{bucket.closed_count}</Td>
                                <Td>
                                  {bucket.tasks.map((task) => (
                                    <Text
                                      key={task.id}
                                      as={task.closed_at ? "s" : undefined}
                                      fontSize="xs"
                                      color={projectTaskColor(task)}
                                      noOfLines={1}
                                    >
                                      <Text
                                        as="button"
                                        textDecoration="underline"
                                        onClick={() => openTaskCard(task.id)}
                                      >
                                        {task.title}
                                      </Text>
                                    </Text>
                                  ))}
                                  {!bucket.tasks.length ? (
                                    <Text fontSize="xs" color="ui.muted">
                                      Нет задач
                                    </Text>
                                  ) : null}
                                </Td>
                              </Tr>
                            )
                          })}
                        </Tbody>
                      </Table>
                    )}
                  </Box>

                  <Box
                    borderWidth="1px"
                    borderColor="ui.border"
                    borderRadius="md"
                    p={4}
                    bg={pageCardBg}
                    mt={4}
                  >
                    <Text fontWeight="700" mb={3}>
                      Распределение задач по участникам проекта
                    </Text>
                    <Box h="320px" minH="320px" minW={0} w="100%">
                      <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={320} debounce={40}>
                        <BarChart data={participantLoad} layout="vertical" margin={{ left: 8 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                          <XAxis type="number" allowDecimals={false} />
                          <YAxis type="category" dataKey="name" width={180} />
                          <Tooltip />
                          <Bar dataKey="count" fill="#2F855A" radius={[0, 6, 6, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </Box>
                    <Text mt={2} fontSize="xs" color="ui.muted">
                      Учитываются только активные задачи: «В работе» и «На проверке».
                    </Text>
                  </Box>
                </GridItem>

                <GridItem>
                  <Box
                    borderWidth="1px"
                    borderColor="ui.border"
                    borderRadius="md"
                    bg={pageCardAltBg}
                    p={4}
                  >
                    <HStack justify="space-between" mb={2}>
                      <Text fontWeight="700" fontSize="sm">Участники проекта</Text>
                      <Button size="xs" variant="subtle" onClick={() => setShowMembersCompact((prev) => !prev)}>
                        {showMembersCompact ? "Скрыть" : "Показать"}
                      </Button>
                    </HStack>
                    <HStack spacing={2} mb={3} flexWrap="wrap">
                      <Badge borderRadius="full" colorScheme="blue" fontSize="11px" px={2} py={0.5}>
                        Всего: {membersSummary.total}
                      </Badge>
                      <Badge borderRadius="full" colorScheme="green" fontSize="11px" px={2} py={0.5}>
                        Активных: {membersSummary.active}
                      </Badge>
                      <Badge borderRadius="full" colorScheme="purple" fontSize="11px" px={2} py={0.5}>
                        Контроллеры: {membersSummary.controllers}
                      </Badge>
                      <Badge borderRadius="full" colorScheme="cyan" fontSize="11px" px={2} py={0.5}>
                        Руководители: {membersSummary.managers}
                      </Badge>
                    </HStack>

                    <Collapse in={showMembersCompact} animateOpacity>
                      {membersLoading ? (
                        <Spinner />
                      ) : (
                        <VStack align="stretch" spacing={2}>
                          {compactMembers.map((member) => (
                            <Box
                              key={member.user_id}
                              borderWidth="1px"
                              borderColor="ui.border"
                              borderRadius="10px"
                              p={2.5}
                            >
                              <HStack justify="space-between" align="start">
                                <Box minW={0}>
                                  <Text fontWeight="700" noOfLines={1}>
                                    {member.user_name}
                                  </Text>
                                  <Text fontSize="sm" color="ui.muted" noOfLines={1}>
                                    {member.user_email}
                                  </Text>
                                </Box>
                                <Badge borderRadius="sm" colorScheme={member.is_active ? "green" : "gray"}>
                                  {projectMemberRoleLabel(member.role)}
                                </Badge>
                              </HStack>
                            </Box>
                          ))}
                          {!compactMembers.length ? (
                            <Text color="ui.muted" fontSize="sm">
                              Нет участников
                            </Text>
                          ) : null}
                        </VStack>
                      )}
                    </Collapse>
                  </Box>
                </GridItem>
              </Grid>
            </TabPanel>

            <TabPanel px={0}>
              <Grid templateColumns={{ base: "1fr", xl: "1fr 1fr" }} gap={4} mb={4}>
                <GridItem>
                  <Box
                    borderWidth="1px"
                    borderColor="ui.border"
                    borderRadius="md"
                    p={4}
                    bg={pageCardBg}
                  >
                    <Text fontSize="xs" color="ui.muted" mb={2}>
                      ОБЩИЕ НАСТРОЙКИ
                    </Text>
                    <Grid templateColumns="1fr 1fr" gap={3}>
                      <GridItem colSpan={2}>
                        <FormControl>
                          <FormLabel>Название проекта</FormLabel>
                          <Input
                            value={policyForm.name}
                            onChange={(e) =>
                              setPolicyForm((prev) => ({
                                ...prev,
                                name: e.target.value,
                              }))
                            }
                          />
                        </FormControl>
                      </GridItem>
                      <GridItem colSpan={2}>
                        <FormControl>
                          <FormLabel>Иконка проекта</FormLabel>
                          <HStack
                            spacing={4}
                            align={{ base: "start", md: "center" }}
                            flexDirection={{ base: "column", md: "row" }}
                          >
                            <Avatar
                              size="lg"
                              name={policyForm.name || project?.name || "Project"}
                              src={resolveProjectIconPath(policyForm.icon)}
                            />
                            <VStack align="start" spacing={2}>
                              <input
                                ref={projectIconInputRef}
                                type="file"
                                accept="image/png,image/jpeg,image/webp,image/svg+xml,image/gif"
                                style={{ display: "none" }}
                                onChange={(event) =>
                                  handleProjectIconPick(event.target.files?.[0] || undefined)
                                }
                              />
                              <HStack spacing={2} flexWrap="wrap">
                                <Button
                                  size="sm"
                                  variant="subtle"
                                  onClick={() => projectIconInputRef.current?.click()}
                                  isLoading={uploadProjectIconMutation.isPending}
                                >
                                  Загрузить файл
                                </Button>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() =>
                                    setPolicyForm((prev) => ({
                                      ...prev,
                                      icon: DEFAULT_PROJECT_ICON_PATH,
                                    }))
                                  }
                                >
                                  Сбросить
                                </Button>
                              </HStack>
                              <Text fontSize="xs" color="ui.muted">
                                Поддерживаются PNG/JPG/WEBP/SVG/GIF, до 2 МБ.
                              </Text>
                            </VStack>
                          </HStack>
                        </FormControl>
                      </GridItem>
                      <GridItem colSpan={2}>
                        <FormControl>
                          <FormLabel>Цвет подсветки проекта</FormLabel>
                          <HStack>
                            <Input
                              type="color"
                              value={projectAccentColor}
                              onChange={(e) => setProjectAccentColor(e.target.value)}
                              w="70px"
                              p={1}
                            />
                            <Text fontSize="sm" color="ui.muted">
                              Используется для подсветки карточек проекта в списке.
                            </Text>
                          </HStack>
                        </FormControl>
                      </GridItem>
                      <GridItem colSpan={2}>
                        <FormControl>
                          <FormLabel>Описание</FormLabel>
                          <Input
                            value={policyForm.description}
                            onChange={(e) =>
                              setPolicyForm((prev) => ({
                                ...prev,
                                description: e.target.value,
                              }))
                            }
                          />
                        </FormControl>
                      </GridItem>
                      <Box>
                        <FormControl display="flex" justifyContent="space-between">
                          <FormLabel m={0}>Комментарий обязателен</FormLabel>
                          <Switch
                            isChecked={policyForm.require_close_comment}
                            onChange={(e) =>
                              setPolicyForm((prev) => ({
                                ...prev,
                                require_close_comment: e.target.checked,
                              }))
                            }
                          />
                        </FormControl>
                      </Box>
                      <Box>
                        <FormControl display="flex" justifyContent="space-between">
                          <FormLabel m={0}>Вложение обязательно</FormLabel>
                          <Switch
                            isChecked={policyForm.require_close_attachment}
                            onChange={(e) =>
                              setPolicyForm((prev) => ({
                                ...prev,
                                require_close_attachment: e.target.checked,
                              }))
                            }
                          />
                        </FormControl>
                      </Box>
                      <FormControl>
                        <FormLabel>Жёлтый порог (дн.)</FormLabel>
                        <NumberInput
                          min={1}
                          value={policyForm.deadline_yellow_days}
                          onChange={(_, value) =>
                            setPolicyForm((prev) => ({
                              ...prev,
                              deadline_yellow_days: Number.isNaN(value) ? 1 : value,
                            }))
                          }
                        >
                          <NumberInputField />
                        </NumberInput>
                      </FormControl>
                      <FormControl>
                        <FormLabel>Зелёный порог (дн.)</FormLabel>
                        <NumberInput
                          min={2}
                          value={policyForm.deadline_normal_days}
                          onChange={(_, value) =>
                            setPolicyForm((prev) => ({
                              ...prev,
                              deadline_normal_days: Number.isNaN(value) ? 2 : value,
                            }))
                          }
                        >
                          <NumberInputField />
                        </NumberInput>
                      </FormControl>
                    </Grid>
                    <HStack mt={3} justify="flex-end">
                      <Button
                        size="sm"
                        onClick={handleSaveProjectSettings}
                        isLoading={updateProjectMutation.isPending}
                      >
                        Сохранить настройки
                      </Button>
                    </HStack>
                  </Box>
                </GridItem>

                <GridItem>
                  <Box borderWidth="1px" borderColor="ui.border" borderRadius="md" bg={pageCardBg}>
                    <Box px={4} py={3} borderBottomWidth="1px" borderColor="ui.border">
                      <HStack justify="space-between">
                        <Text fontWeight="700">Участники проекта</Text>
                        <Badge borderRadius="full">{visibleMembers.length}</Badge>
                      </HStack>
                    </Box>
                    <Box p={4}>
                      {canManageAccess ? (
                        <Grid templateColumns={{ base: "1fr", md: "1.3fr 1fr auto" }} gap={2} mb={3}>
                          <Select
                            placeholder="Добавить участника"
                            value={newMemberUserId}
                            onChange={(event) => setNewMemberUserId(event.target.value)}
                          >
                            {availableMemberOptions.map((user) => (
                              <option key={user.id} value={user.id}>
                                {user.label} ({user.email})
                              </option>
                            ))}
                          </Select>
                          <Select
                            value={newMemberRole}
                            onChange={(event) =>
                              setNewMemberRole(event.target.value as MemberRoleKey)
                            }
                          >
                            <option value="reader">Читатель</option>
                            <option value="executor">Исполнитель</option>
                            <option value="controller">Контроллер</option>
                            <option value="manager">Руководитель</option>
                          </Select>
                          <Button onClick={addProjectMember} isDisabled={!newMemberUserId} variant="subtle">
                            Добавить
                          </Button>
                        </Grid>
                      ) : null}

                      {membersLoading ? (
                        <Spinner />
                      ) : (
                        <Table size="sm">
                          <Thead>
                            <Tr>
                              <Th>Пользователь</Th>
                              <Th>Email</Th>
                              <Th>Роль</Th>
                              <Th>Активен</Th>
                              {canManageAccess ? <Th textAlign="right">Действия</Th> : null}
                            </Tr>
                          </Thead>
                          <Tbody>
                            {projectMembersDraft
                              .filter((row) => !row.is_removed)
                              .map((row) => (
                                <Tr key={row.user_id}>
                                  <Td>{row.user_name}</Td>
                                  <Td>{row.user_email}</Td>
                                  <Td>
                                    {canManageAccess ? (
                                      <Select
                                        size="xs"
                                        value={row.role}
                                        onChange={(event) =>
                                          setProjectMembersDraft((prev) =>
                                            prev.map((item) =>
                                              item.user_id === row.user_id
                                                ? {
                                                    ...item,
                                                    role: event.target.value as MemberRoleKey,
                                                  }
                                                : item,
                                            ),
                                          )
                                        }
                                      >
                                        <option value="reader">Читатель</option>
                                        <option value="executor">Исполнитель</option>
                                        <option value="controller">Контроллер</option>
                                        <option value="manager">Руководитель</option>
                                      </Select>
                                    ) : (
                                      <Text>{projectMemberRoleLabel(row.role)}</Text>
                                    )}
                                  </Td>
                                  <Td>
                                    <Badge colorScheme={row.is_active ? "green" : "gray"}>
                                      {row.is_active ? "Да" : "Нет"}
                                    </Badge>
                                  </Td>
                                  {canManageAccess ? (
                                    <Td textAlign="right">
                                      <HStack justify="flex-end">
                                        <Button
                                          size="xs"
                                          variant="subtle"
                                          onClick={() =>
                                            setProjectMembersDraft((prev) =>
                                              prev.map((item) =>
                                                item.user_id === row.user_id
                                                  ? { ...item, is_active: !item.is_active }
                                                  : item,
                                              ),
                                            )
                                          }
                                        >
                                          {row.is_active ? "Отключить" : "Включить"}
                                        </Button>
                                        <Button
                                          size="xs"
                                          variant="subtle"
                                          colorScheme="red"
                                          onClick={() =>
                                            setProjectMembersDraft((prev) =>
                                              prev.map((item) =>
                                                item.user_id === row.user_id
                                                  ? { ...item, is_removed: true }
                                                  : item,
                                              ),
                                            )
                                          }
                                        >
                                          Удалить
                                        </Button>
                                      </HStack>
                                    </Td>
                                  ) : null}
                                </Tr>
                              ))}
                            {!visibleMembers.length ? (
                              <Tr>
                                <Td colSpan={canManageAccess ? 5 : 4}>
                                  <Text color="ui.muted">Нет участников проекта</Text>
                                </Td>
                              </Tr>
                            ) : null}
                          </Tbody>
                        </Table>
                      )}
                      {canManageAccess ? (
                        <HStack justify="flex-end" mt={3}>
                          <Button
                            size="sm"
                            onClick={() => saveProjectMembersMutation.mutate()}
                            isLoading={saveProjectMembersMutation.isPending}
                          >
                            Сохранить участников
                          </Button>
                        </HStack>
                      ) : null}
                    </Box>
                  </Box>
                </GridItem>
              </Grid>

              <Grid templateColumns={{ base: "1fr", xl: "1fr 1fr" }} gap={4}>
                <GridItem>
                  <Box borderWidth="1px" borderColor="ui.border" borderRadius="md" bg={pageCardBg}>
                    <Box px={4} py={3} borderBottomWidth="1px" borderColor="ui.border">
                      <HStack justify="space-between">
                        <Text fontWeight="700">Доступ пользователей</Text>
                        <Badge borderRadius="full">{accessUsersDraft.length}</Badge>
                      </HStack>
                    </Box>
                    <Box p={4}>
                      {canManageAccess ? (
                        <Grid templateColumns={{ base: "1fr", md: "1.3fr 1fr auto" }} gap={2} mb={3}>
                          <Select
                            placeholder="Добавить пользователя"
                            value={newAccessUserId}
                            onChange={(event) => setNewAccessUserId(event.target.value)}
                          >
                            {availableUserOptions.map((user) => (
                              <option key={user.id} value={user.id}>
                                {user.label} ({user.email})
                              </option>
                            ))}
                          </Select>
                          <Select
                            value={newAccessUserRole}
                            onChange={(event) =>
                              setNewAccessUserRole(event.target.value as AccessRoleKey)
                            }
                          >
                            <option value="reader">Читатель</option>
                            <option value="contributor">Контрибьютор</option>
                            <option value="project_admin">Администратор проекта</option>
                          </Select>
                          <Button onClick={addAccessUser} isDisabled={!newAccessUserId} variant="subtle">
                            Добавить
                          </Button>
                        </Grid>
                      ) : null}

                      {accessUsersLoading ? (
                        <Spinner />
                      ) : (
                        <Table size="sm">
                          <Thead>
                            <Tr>
                              <Th>Пользователь</Th>
                              <Th>Email</Th>
                              <Th>Роль</Th>
                              <Th>Активен</Th>
                              {canManageAccess ? <Th textAlign="right">Действия</Th> : null}
                            </Tr>
                          </Thead>
                          <Tbody>
                            {accessUsersDraft.map((row) => (
                              <Tr key={row.user_id}>
                                <Td>{row.user_name}</Td>
                                <Td>{row.user_email}</Td>
                                <Td>
                                  {canManageAccess ? (
                                    <Select
                                      size="xs"
                                      value={row.role_key}
                                      onChange={(event) =>
                                        setAccessUsersDraft((prev) =>
                                          prev.map((item) =>
                                            item.user_id === row.user_id
                                              ? {
                                                  ...item,
                                                  role_key: event.target.value as AccessRoleKey,
                                                }
                                              : item,
                                          ),
                                        )
                                      }
                                    >
                                      <option value="reader">Читатель</option>
                                      <option value="contributor">Контрибьютор</option>
                                      <option value="project_admin">Администратор проекта</option>
                                    </Select>
                                  ) : (
                                    <Text>{accessRoleLabel(row.role_key)}</Text>
                                  )}
                                </Td>
                                <Td>
                                  <Badge colorScheme={row.is_active ? "green" : "gray"}>
                                    {row.is_active ? "Да" : "Нет"}
                                  </Badge>
                                </Td>
                                {canManageAccess ? (
                                  <Td textAlign="right">
                                    <HStack justify="flex-end">
                                      <Button
                                        size="xs"
                                        variant="subtle"
                                        onClick={() =>
                                          setAccessUsersDraft((prev) =>
                                            prev.map((item) =>
                                              item.user_id === row.user_id
                                                ? { ...item, is_active: !item.is_active }
                                                : item,
                                            ),
                                          )
                                        }
                                      >
                                        {row.is_active ? "Отключить" : "Включить"}
                                      </Button>
                                      <Button
                                        size="xs"
                                        variant="subtle"
                                        colorScheme="red"
                                        onClick={() =>
                                          setAccessUsersDraft((prev) =>
                                            prev.filter((item) => item.user_id !== row.user_id),
                                          )
                                        }
                                      >
                                        Удалить
                                      </Button>
                                    </HStack>
                                  </Td>
                                ) : null}
                              </Tr>
                            ))}
                            {!accessUsersDraft.length ? (
                              <Tr>
                                <Td colSpan={canManageAccess ? 5 : 4}>
                                  <Text color="ui.muted">Нет назначенных пользователей</Text>
                                </Td>
                              </Tr>
                            ) : null}
                          </Tbody>
                        </Table>
                      )}

                      {canManageAccess ? (
                        <HStack justify="flex-end" mt={3}>
                          <Button
                            size="sm"
                            onClick={() => saveAccessUsersMutation.mutate()}
                            isLoading={saveAccessUsersMutation.isPending}
                          >
                            Сохранить доступ пользователей
                          </Button>
                        </HStack>
                      ) : null}
                    </Box>
                  </Box>
                </GridItem>

                <GridItem>
                  <Box borderWidth="1px" borderColor="ui.border" borderRadius="md" bg={pageCardBg}>
                    <Box px={4} py={3} borderBottomWidth="1px" borderColor="ui.border">
                      <HStack justify="space-between">
                        <Text fontWeight="700">Доступ групп</Text>
                        <Badge borderRadius="full">{accessGroupsDraft.length}</Badge>
                      </HStack>
                    </Box>
                    <Box p={4}>
                      {canManageAccess ? (
                        <Grid templateColumns={{ base: "1fr", md: "1.3fr 1fr auto" }} gap={2} mb={3}>
                          <Select
                            placeholder="Добавить группу"
                            value={newAccessGroupId}
                            onChange={(event) => setNewAccessGroupId(event.target.value)}
                          >
                            {availableGroupOptions.map((group) => (
                              <option key={group.id} value={group.id}>
                                {group.name} ({group.organization_name})
                              </option>
                            ))}
                          </Select>
                          <Select
                            value={newAccessGroupRole}
                            onChange={(event) =>
                              setNewAccessGroupRole(event.target.value as AccessRoleKey)
                            }
                          >
                            <option value="reader">Читатель</option>
                            <option value="contributor">Контрибьютор</option>
                            <option value="project_admin">Администратор проекта</option>
                          </Select>
                          <Button onClick={addAccessGroup} isDisabled={!newAccessGroupId} variant="subtle">
                            Добавить
                          </Button>
                        </Grid>
                      ) : null}

                      {accessGroupsLoading ? (
                        <Spinner />
                      ) : (
                        <Table size="sm">
                          <Thead>
                            <Tr>
                              <Th>Группа</Th>
                              <Th>Организация</Th>
                              <Th>Роль</Th>
                              <Th>Активна</Th>
                              {canManageAccess ? <Th textAlign="right">Действия</Th> : null}
                            </Tr>
                          </Thead>
                          <Tbody>
                            {accessGroupsDraft.map((group) => (
                              <Tr key={group.group_id}>
                                <Td>{group.group_name}</Td>
                                <Td>{group.organization_name}</Td>
                                <Td>
                                  {canManageAccess ? (
                                    <Select
                                      size="xs"
                                      value={group.role_key}
                                      onChange={(event) =>
                                        setAccessGroupsDraft((prev) =>
                                          prev.map((item) =>
                                            item.group_id === group.group_id
                                              ? {
                                                  ...item,
                                                  role_key: event.target.value as AccessRoleKey,
                                                }
                                              : item,
                                          ),
                                        )
                                      }
                                    >
                                      <option value="reader">Читатель</option>
                                      <option value="contributor">Контрибьютор</option>
                                      <option value="project_admin">Администратор проекта</option>
                                    </Select>
                                  ) : (
                                    <Text>{accessRoleLabel(group.role_key)}</Text>
                                  )}
                                </Td>
                                <Td>
                                  <Badge colorScheme={group.is_active ? "green" : "gray"}>
                                    {group.is_active ? "Да" : "Нет"}
                                  </Badge>
                                </Td>
                                {canManageAccess ? (
                                  <Td textAlign="right">
                                    <HStack justify="flex-end">
                                      <Button
                                        size="xs"
                                        variant="subtle"
                                        onClick={() =>
                                          setAccessGroupsDraft((prev) =>
                                            prev.map((item) =>
                                              item.group_id === group.group_id
                                                ? { ...item, is_active: !item.is_active }
                                                : item,
                                            ),
                                          )
                                        }
                                      >
                                        {group.is_active ? "Отключить" : "Включить"}
                                      </Button>
                                      <Button
                                        size="xs"
                                        variant="subtle"
                                        colorScheme="red"
                                        onClick={() =>
                                          setAccessGroupsDraft((prev) =>
                                            prev.filter((item) => item.group_id !== group.group_id),
                                          )
                                        }
                                      >
                                        Удалить
                                      </Button>
                                    </HStack>
                                  </Td>
                                ) : null}
                              </Tr>
                            ))}
                            {!accessGroupsDraft.length ? (
                              <Tr>
                                <Td colSpan={canManageAccess ? 5 : 4}>
                                  <Text color="ui.muted">Нет назначенных групп</Text>
                                </Td>
                              </Tr>
                            ) : null}
                          </Tbody>
                        </Table>
                      )}

                      {canManageAccess ? (
                        <HStack justify="flex-end" mt={3}>
                          <Button
                            size="sm"
                            onClick={() => saveAccessGroupsMutation.mutate()}
                            isLoading={saveAccessGroupsMutation.isPending}
                          >
                            Сохранить доступ групп
                          </Button>
                        </HStack>
                      ) : null}
                    </Box>
                  </Box>
                </GridItem>
              </Grid>
            </TabPanel>
          </TabPanels>
        </Tabs>
      )}

      <Drawer isOpen={dayDrawer.isOpen} placement="right" onClose={dayDrawer.onClose} size="xl">
        <DrawerOverlay />
        <DrawerContent bg={drawerBg} color={drawerTextColor}>
          <DrawerCloseButton />
          <DrawerHeader bg={drawerHeaderBg} borderBottomWidth="1px" borderColor="ui.border">
            Задачи проекта на {selectedDay || "-"}
          </DrawerHeader>
          <DrawerBody>
            {dayTabs.length > 0 && (
              <HStack spacing={2} overflowX="auto" pb={2} mb={3}>
                {dayTabs.map((dayKey) => {
                  const bucket = bucketsByDay.get(dayKey)
                  const isActive = selectedDay === dayKey
                  const formatted = new Date(dayKey).toLocaleDateString("ru-RU", {
                    day: "2-digit",
                    month: "2-digit",
                  })
                  return (
                    <Button
                      key={dayKey}
                      size="sm"
                      bg={isActive ? "ui.main" : dayTabInactiveBg}
                      color={isActive ? "white" : dayTabInactiveColor}
                      _hover={{
                        bg: isActive ? "ui.main" : dayTabInactiveHoverBg,
                      }}
                      onClick={() => setSelectedDay(dayKey)}
                      whiteSpace="nowrap"
                      minW="110px"
                      fontSize="xs"
                    >
                      {formatted} ({bucket?.total_count ?? 0})
                    </Button>
                  )
                })}
              </HStack>
            )}

            {!selectedBucket?.total_count && <Text color="ui.muted">Нет задач на выбранный день</Text>}
            {(selectedBucket?.total_count ?? 0) > 0 && (
              <VStack align="stretch" spacing={2}>
                {(selectedBucket?.tasks ?? []).map((task) => (
                  <Box
                    key={task.id}
                    borderWidth="1px"
                    borderColor="ui.border"
                    borderRadius="10px"
                    borderLeftWidth="4px"
                    borderLeftColor={projectTaskAccentColor(task)}
                    bg={projectTaskCardBackground(task)}
                    px={3}
                    py={2.5}
                  >
                    <HStack justify="space-between" align="start" gap={3}>
                      <Box minW={0}>
                        <Text as={task.closed_at ? "s" : undefined} fontWeight="700" noOfLines={1}>
                          <Text as="button" textDecoration="underline" onClick={() => openTaskCard(task.id)}>
                            {task.title}
                          </Text>
                        </Text>
                        <Text fontSize="sm" color="ui.muted" noOfLines={1}>
                          {task.assignee_name || "Без исполнителя"} • {task.status_name || "Без статуса"}
                        </Text>
                      </Box>
                      <VStack spacing={1} align="end">
                        <Badge borderRadius="full" bg={projectTaskAccentColor(task)} color="white">
                          {projectTaskDeadlineLabel(task)}
                        </Badge>
                        <Text fontSize="xs" color="ui.darkSlate">
                          {new Date(task.due_date).toLocaleString("ru-RU")}
                        </Text>
                      </VStack>
                    </HStack>
                  </Box>
                ))}
              </VStack>
            )}
          </DrawerBody>
        </DrawerContent>
      </Drawer>
    </Container>
  )
}

function MetricTile({ label, value }: { label: string; value: number }) {
  return (
    <Box bg="whiteAlpha.180" borderRadius="12px" px={3} py={2}>
      <Text fontSize="xs" color="whiteAlpha.800">
        {label}
      </Text>
      <Text fontSize="xl" fontWeight="700">
        {value}
      </Text>
    </Box>
  )
}

function StatPanel({
  title,
  value,
  valueColor,
}: {
  title: string
  value: number
  valueColor?: string
}) {
  const panelBg = useColorModeValue("white", "#162235")
  return (
    <Box borderWidth="1px" borderColor="ui.border" borderRadius="md" p={3} bg={panelBg}>
      <Text fontSize="xs" color="ui.muted">
        {title}
      </Text>
      <Text fontSize="2xl" fontWeight="700" color={valueColor}>
        {value}
      </Text>
    </Box>
  )
}

function projectMemberRoleLabel(role: MemberRoleKey): string {
  if (role === "manager") return "Руководитель"
  if (role === "controller") return "Контроллер"
  if (role === "reader") return "Читатель"
  return "Исполнитель"
}

function accessRoleLabel(role: AccessRoleKey): string {
  if (role === "project_admin") return "Администратор проекта"
  if (role === "contributor") return "Контрибьютор"
  return "Читатель"
}

function shiftCalendarDate(
  rawDate: string,
  mode: "day" | "week" | "month",
  direction: -1 | 1,
): string {
  const value = new Date(rawDate)
  if (mode === "day") {
    value.setDate(value.getDate() + direction)
  } else if (mode === "week") {
    value.setDate(value.getDate() + direction * 7)
  } else {
    value.setMonth(value.getMonth() + direction)
  }
  return value.toISOString().slice(0, 10)
}

function toYmd(value: Date): string {
  const year = value.getFullYear()
  const month = `${value.getMonth() + 1}`.padStart(2, "0")
  const day = `${value.getDate()}`.padStart(2, "0")
  return `${year}-${month}-${day}`
}

function startOfWeekMonday(value: Date): Date {
  const day = new Date(value)
  const dayOfWeek = (day.getDay() + 6) % 7
  day.setDate(day.getDate() - dayOfWeek)
  day.setHours(0, 0, 0, 0)
  return day
}

function endOfWeekSunday(value: Date): Date {
  const day = new Date(value)
  const dayOfWeek = (day.getDay() + 6) % 7
  day.setDate(day.getDate() + (6 - dayOfWeek))
  day.setHours(23, 59, 59, 999)
  return day
}

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1)
}

function calendarCellColor(bucket?: CalendarViewBucket): string {
  if (!bucket?.total_count) return "#FFFFFF"
  if (bucket.overdue_count > 0) return "#FDECEC"
  return "#F4FBF5"
}

function projectTaskColor(task: {
  closed_at?: string | null
  is_overdue: boolean
  computed_deadline_state: "green" | "yellow" | "red"
  closed_overdue: boolean
}): string {
  if (task.closed_at && task.closed_overdue) return "#C62828"
  if (task.closed_at) return "#6b7280"
  if (task.is_overdue || task.computed_deadline_state === "red") return "#C62828"
  if (task.computed_deadline_state === "yellow") return "#B7791F"
  return "#2F855A"
}

function projectTaskAccentColor(task: CalendarDayTask): string {
  if (task.closed_at && task.closed_overdue) return "#C62828"
  if (task.closed_at) return "#6b7280"
  if (task.is_overdue || task.computed_deadline_state === "red") return "#C62828"
  if (task.computed_deadline_state === "yellow") return "#B7791F"
  return "#2F855A"
}

function projectTaskCardBackground(task: CalendarDayTask): string {
  if (task.closed_at) return "#F7F8FA"
  if (task.is_overdue || task.computed_deadline_state === "red") return "#FFF4F4"
  if (task.computed_deadline_state === "yellow") return "#FFF8E8"
  return "#F3FBF5"
}

function projectTaskDeadlineLabel(task: CalendarDayTask): string {
  if (task.closed_at && task.closed_overdue) return "Закрыта с просрочкой"
  if (task.closed_at) return "Закрыта"
  if (task.is_overdue || task.computed_deadline_state === "red") return "Просрочено"
  if (task.computed_deadline_state === "yellow") return "Критично"
  return "В срок"
}

function openTaskCard(taskId: number) {
  window.location.assign(`/tasks?taskId=${taskId}`)
}
