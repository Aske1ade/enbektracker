import {
  Badge,
  Box,
  Button,
  Container,
  Collapse,
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
  Input,
  Select,
  Spinner,
  Table,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tr,
  Tooltip,
  VStack,
  useColorModeValue,
  useDisclosure,
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { useMemo, useState } from "react"
import { FiInfo } from "react-icons/fi"

import { trackerApi } from "../../services/trackerApi"
import type {
  CalendarDayTask,
  CalendarScope,
  CalendarViewBucket,
  CalendarViewMode,
} from "../../types/tracker"

export const Route = createFileRoute("/_layout/calendar")({
  component: CalendarPage,
})

function CalendarPage() {
  const navigate = useNavigate()
  const cardBg = useColorModeValue("white", "#162235")
  const cardAltBg = useColorModeValue("white", "#142033")
  const drawerBg = useColorModeValue("white", "#101b2f")
  const drawerHeaderBg = useColorModeValue("white", "#15263f")
  const drawerTextColor = useColorModeValue("ui.text", "ui.light")
  const dayTabInactiveBg = useColorModeValue("rgba(234,240,248,0.9)", "#1A2B44")
  const dayTabInactiveColor = useColorModeValue("ui.main", "ui.light")
  const dayTabInactiveHoverBg = useColorModeValue("#dbe7f6", "#233a5d")
  const [anchorDate, setAnchorDate] = useState(() => new Date())
  const [mode, setMode] = useState<CalendarViewMode>("month")
  const [scope, setScope] = useState<CalendarScope>("project")
  const [projectId, setProjectId] = useState("")
  const [departmentId, setDepartmentId] = useState("")
  const [projectSearch, setProjectSearch] = useState("")
  const [departmentSearch, setDepartmentSearch] = useState("")
  const [showFilters, setShowFilters] = useState(false)
  const [selectedDay, setSelectedDay] = useState<string | null>(null)
  const dayDrawer = useDisclosure()

  const projectNumber = projectId ? Number(projectId) : undefined
  const departmentNumber = departmentId ? Number(departmentId) : undefined

  const { data: projectsData } = useQuery({
    queryKey: ["projects-for-calendar"],
    queryFn: () =>
      trackerApi.listProjects({
        page: 1,
        page_size: 300,
        sort_by: "name",
        sort_order: "asc",
      }),
  })

  const { data: departmentsData } = useQuery({
    queryKey: ["departments-for-calendar"],
    queryFn: () => trackerApi.listDepartments(),
  })

  const filteredProjects = useMemo(() => {
    const query = projectSearch.trim().toLowerCase()
    if (!query) return projectsData?.data ?? []
    return (projectsData?.data ?? []).filter((project) =>
      project.name.toLowerCase().includes(query),
    )
  }, [projectSearch, projectsData?.data])

  const filteredDepartments = useMemo(() => {
    const query = departmentSearch.trim().toLowerCase()
    if (!query) return departmentsData?.data ?? []
    return (departmentsData?.data ?? []).filter((department) =>
      department.name.toLowerCase().includes(query),
    )
  }, [departmentSearch, departmentsData?.data])

  const { data: calendarView, isLoading } = useQuery({
    queryKey: [
      "calendar-view",
      toYmd(anchorDate),
      mode,
      scope,
      projectNumber,
      departmentNumber,
    ],
    queryFn: () =>
      trackerApi.calendarView({
        date: toYmd(anchorDate),
        mode,
        scope,
        project_id: scope === "project" ? projectNumber : undefined,
        department_id: departmentNumber,
      }),
  })

  const bucketsByDay = useMemo(() => {
    const map = new Map<string, CalendarViewBucket>()
    for (const bucket of calendarView?.data ?? []) {
      map.set(String(bucket.day).slice(0, 10), bucket)
    }
    return map
  }, [calendarView])

  const selectedBucket = selectedDay ? bucketsByDay.get(selectedDay) : undefined
  const dayTabs = useMemo(
    () =>
      (calendarView?.data ?? [])
        .map((bucket) => String(bucket.day).slice(0, 10))
        .sort((a, b) => a.localeCompare(b)),
    [calendarView?.data],
  )

  const monthStart = new Date(anchorDate.getFullYear(), anchorDate.getMonth(), 1)
  const monthEnd = new Date(anchorDate.getFullYear(), anchorDate.getMonth() + 1, 0)
  const gridStart = startOfWeekMonday(monthStart)
  const gridEnd = endOfWeekSunday(monthEnd)

  const gridDays = useMemo(() => {
    const days: Date[] = []
    const current = new Date(gridStart)
    while (current <= gridEnd) {
      days.push(new Date(current))
      current.setDate(current.getDate() + 1)
    }
    return days
  }, [gridStart, gridEnd])

  const headerLabel = useMemo(() => {
    if (mode === "day") {
      return anchorDate.toLocaleDateString("ru-RU", {
        day: "2-digit",
        month: "long",
        year: "numeric",
      })
    }
    if (mode === "week") {
      const from = calendarView?.date_from
      const to = calendarView?.date_to
      if (!from || !to) return "Неделя"
      return `${new Date(from).toLocaleDateString("ru-RU")} - ${new Date(
        to,
      ).toLocaleDateString("ru-RU")}`
    }
    if (mode === "year") {
      return String(anchorDate.getFullYear())
    }
    return capitalize(
      anchorDate.toLocaleDateString("ru-RU", {
        month: "long",
        year: "numeric",
      }),
    )
  }, [anchorDate, calendarView?.date_from, calendarView?.date_to, mode])

  const renderMonth = () => (
    <Box
      borderWidth="1px"
      borderColor="ui.border"
      borderRadius="md"
      overflow="hidden"
      bg={cardBg}
    >
      <Grid
        templateColumns="repeat(7, minmax(0, 1fr))"
        borderBottomWidth="1px"
        borderColor="ui.border"
      >
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
          const totalCount = bucket?.total_count ?? 0
          const preview = bucket?.tasks.slice(0, 3) ?? []
          const inCurrentMonth = day.getMonth() === anchorDate.getMonth()
          const isToday = dayKey === toYmd(new Date())
          return (
            <Box
              key={`${dayKey}-${index}`}
              minH="150px"
              borderRightWidth={(index + 1) % 7 === 0 ? "0" : "1px"}
              borderBottomWidth="1px"
              borderColor={isToday ? "#1E3A5F" : "ui.border"}
              p={2}
              bg={calendarCellColor(bucket)}
              opacity={inCurrentMonth ? 1 : 0.45}
              cursor={totalCount > 0 ? "pointer" : "default"}
              onClick={() => {
                if (!totalCount) return
                setSelectedDay(dayKey)
                dayDrawer.onOpen()
              }}
            >
              <HStack justify="space-between" align="start" mb={1}>
                <Text fontSize="md" fontWeight="700">
                  {day.getDate()}
                </Text>
                {isToday ? (
                  <Badge colorScheme="blue" borderRadius="sm">
                    Сегодня
                  </Badge>
                ) : null}
              </HStack>

              {totalCount ? (
                <>
                  <Text fontSize="xs" color="ui.muted" mb={1}>
                    Всего: {totalCount}
                  </Text>
                  {preview.map((task) => (
                    <Text
                      key={task.id}
                      as={task.closed_at ? "s" : undefined}
                      fontSize="xs"
                      color={taskRowColor(task)}
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
                      cursor="pointer"
                      onClick={(event) => {
                        event.stopPropagation()
                        setAnchorDate(new Date(`${dayKey}T00:00:00`))
                        setMode("day")
                      }}
                    >
                      +{totalCount - preview.length} задач
                    </Text>
                  ) : null}
                </>
              ) : (
                <Text fontSize="xs" color="ui.dim">
                  Без задач
                </Text>
              )}
            </Box>
          )
        })}
      </Grid>
    </Box>
  )

  const renderWeekOrDay = () => (
    <Box
      borderWidth="1px"
      borderColor="ui.border"
      borderRadius="md"
      overflow="hidden"
      bg={cardBg}
    >
      <Table size="sm">
        <Thead>
          <Tr>
            <Th>Дата</Th>
            <Th>Задачи</Th>
            <Th>Просроченные</Th>
            <Th>Закрытые</Th>
            <Th>Действие</Th>
          </Tr>
        </Thead>
        <Tbody>
          {(calendarView?.data ?? []).map((bucket) => {
            const dayKey = String(bucket.day).slice(0, 10)
            return (
              <Tr key={dayKey}>
                <Td>{new Date(dayKey).toLocaleDateString("ru-RU")}</Td>
                <Td>{bucket.total_count}</Td>
                <Td>{bucket.overdue_count}</Td>
                <Td>{bucket.closed_count}</Td>
                <Td>
                  <Button
                    size="xs"
                    onClick={() => {
                      setSelectedDay(dayKey)
                      dayDrawer.onOpen()
                    }}
                    isDisabled={!bucket.total_count}
                  >
                    Открыть день
                  </Button>
                </Td>
              </Tr>
            )
          })}
        </Tbody>
      </Table>
    </Box>
  )

  const renderYear = () => {
    const monthlyBuckets = new Map<
      number,
      { total: number; overdue: number; closed: number }
    >()
    for (const bucket of calendarView?.data ?? []) {
      const monthIndex = new Date(String(bucket.day)).getMonth()
      const current = monthlyBuckets.get(monthIndex) ?? {
        total: 0,
        overdue: 0,
        closed: 0,
      }
      current.total += bucket.total_count
      current.overdue += bucket.overdue_count
      current.closed += bucket.closed_count
      monthlyBuckets.set(monthIndex, current)
    }

    return (
      <Grid templateColumns={{ base: "1fr", md: "repeat(3, 1fr)", xl: "repeat(4, 1fr)" }} gap={3}>
        {Array.from({ length: 12 }).map((_, monthIndex) => {
          const stats = monthlyBuckets.get(monthIndex) ?? {
            total: 0,
            overdue: 0,
            closed: 0,
          }
          const monthDate = new Date(anchorDate.getFullYear(), monthIndex, 1)
          return (
            <Box
              key={`year-month-${monthIndex}`}
              borderWidth="1px"
              borderColor="ui.border"
              borderRadius="10px"
              p={3}
              bg={cardBg}
            >
              <HStack justify="space-between" mb={2}>
                <Text fontWeight="700">
                  {monthDate.toLocaleDateString("ru-RU", { month: "long" })}
                </Text>
                <Button
                  size="xs"
                  variant="subtle"
                  onClick={() => {
                    setAnchorDate(monthDate)
                    setMode("month")
                  }}
                >
                  Открыть
                </Button>
              </HStack>
              <Text fontSize="sm" color="ui.darkSlate">
                Всего задач: {stats.total}
              </Text>
              <Text fontSize="sm" color="#A61B1B">
                Просрочено: {stats.overdue}
              </Text>
              <Text fontSize="sm" color="ui.muted">
                Закрыто: {stats.closed}
              </Text>
            </Box>
          )
        })}
      </Grid>
    )
  }

  return (
    <Container maxW="full" py={6}>
      <HStack justify="space-between" mb={4} flexWrap="wrap" gap={3}>
        <HStack align="center" spacing={2}>
          <Heading size="lg">Календарь задач</Heading>
          <Tooltip
            hasArrow
            placement="right"
            label="Режимы день/неделя/месяц/год, переключение на мой календарь и детальный просмотр задач дня"
          >
            <Box color="ui.muted" cursor="help">
              <Icon as={FiInfo} />
            </Box>
          </Tooltip>
        </HStack>
        <HStack>
          <HStack spacing={1}>
            {[
              { value: "day", label: "День" },
              { value: "week", label: "Неделя" },
              { value: "month", label: "Месяц" },
              { value: "year", label: "Год" },
            ].map((item) => (
              <Button
                key={`mode-${item.value}`}
                size="sm"
                variant={mode === item.value ? "primary" : "subtle"}
                onClick={() => setMode(item.value as CalendarViewMode)}
              >
                {item.label}
              </Button>
            ))}
          </HStack>
          <Button
            size="sm"
            variant="subtle"
            onClick={() => setAnchorDate(shiftDate(anchorDate, mode, -1))}
          >
            ←
          </Button>
          <Text minW="260px" textAlign="center" fontWeight="700">
            {headerLabel}
          </Text>
          <Button
            size="sm"
            variant="subtle"
            onClick={() => setAnchorDate(shiftDate(anchorDate, mode, 1))}
          >
            →
          </Button>
          <Button
            size="sm"
            variant="subtle"
            onClick={() => setShowFilters((prev) => !prev)}
          >
            {showFilters ? "Скрыть фильтры" : "Показать фильтры"}
          </Button>
        </HStack>
      </HStack>

      <Collapse in={showFilters} animateOpacity>
        <Grid templateColumns={{ base: "1fr", xl: "1.2fr 1fr" }} gap={4} mb={4}>
          <Box
            borderWidth="1px"
            borderColor="ui.border"
            borderRadius="md"
            p={4}
            bg={cardBg}
          >
            <HStack justify="space-between" mb={3}>
              <Heading size="sm">Фильтры календаря</Heading>
              <Button size="xs" variant="subtle" onClick={() => setShowFilters(false)}>
                Свернуть
              </Button>
            </HStack>
          <HStack mb={3} flexWrap="wrap">
            <FormControl w={{ base: "100%", md: "170px" }}>
              <FormLabel>Режим</FormLabel>
              <Select
                value={mode}
                onChange={(event) => setMode(event.target.value as CalendarViewMode)}
              >
                <option value="day">День</option>
                <option value="week">Неделя</option>
                <option value="month">Месяц</option>
                <option value="year">Год</option>
              </Select>
            </FormControl>
            <FormControl w={{ base: "100%", md: "220px" }}>
              <FormLabel>Область</FormLabel>
              <Select
                value={scope}
                onChange={(event) => setScope(event.target.value as CalendarScope)}
              >
                <option value="project">Календарь проекта</option>
                <option value="my">Мой календарь</option>
              </Select>
            </FormControl>
            <FormControl w={{ base: "100%", md: "170px" }}>
              <FormLabel>Дата</FormLabel>
              <Input
                type="date"
                value={toYmd(anchorDate)}
                onChange={(event) => setAnchorDate(new Date(event.target.value))}
              />
            </FormControl>
          </HStack>

          <Grid templateColumns={{ base: "1fr", md: "1fr 1fr" }} gap={3}>
            <FormControl>
              <FormLabel>Проект</FormLabel>
              <Input
                placeholder="Поиск проекта"
                value={projectSearch}
                onChange={(event) => setProjectSearch(event.target.value)}
                mb={2}
                isDisabled={scope === "my"}
              />
              <Select
                value={projectId}
                onChange={(event) => setProjectId(event.target.value)}
                isDisabled={scope === "my"}
              >
                <option value="">Все проекты</option>
                {filteredProjects.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                  </option>
                ))}
              </Select>
            </FormControl>

            <FormControl>
              <FormLabel>Департамент</FormLabel>
              <Input
                placeholder="Поиск департамента"
                value={departmentSearch}
                onChange={(event) => setDepartmentSearch(event.target.value)}
                mb={2}
              />
              <Select
                value={departmentId}
                onChange={(event) => setDepartmentId(event.target.value)}
              >
                <option value="">Все департаменты</option>
                {filteredDepartments.map((department) => (
                  <option key={department.id} value={department.id}>
                    {department.name}
                  </option>
                ))}
              </Select>
            </FormControl>
          </Grid>
          </Box>

          <Box
            borderWidth="1px"
            borderColor="ui.border"
            borderRadius="md"
            p={4}
            bg={cardAltBg}
          >
            <Text fontWeight="700" mb={2}>
              Легенда
            </Text>
            <Text fontSize="sm" color="ui.darkSlate">
              Зеленый: в срок, желтый: срок близко, красный: просрочено.
              Закрытые задачи отображаются зачеркнутыми.
            </Text>
          </Box>
        </Grid>
      </Collapse>

      <Box minH="calc(100vh - 220px)">
        {isLoading ? (
          <Spinner />
        ) : mode === "month" ? (
          renderMonth()
        ) : mode === "year" ? (
          renderYear()
        ) : (
          renderWeekOrDay()
        )}
      </Box>

      <Drawer isOpen={dayDrawer.isOpen} placement="right" onClose={dayDrawer.onClose} size="xl">
        <DrawerOverlay />
        <DrawerContent bg={drawerBg} color={drawerTextColor}>
          <DrawerCloseButton />
          <DrawerHeader bg={drawerHeaderBg} borderBottomWidth="1px" borderColor="ui.border">
            Задачи на {selectedDay || "-"}
          </DrawerHeader>
          <DrawerBody>
            {dayTabs.length > 0 && (
              <HStack spacing={2} flexWrap="wrap" align="stretch" pb={2} mb={3}>
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
                      minW="112px"
                      h="34px"
                      fontSize="xs"
                    >
                      {formatted} · {bucket?.total_count ?? 0}
                    </Button>
                  )
                })}
              </HStack>
            )}

            {!selectedBucket?.total_count && (
              <Text color="ui.muted">Нет задач на выбранный день</Text>
            )}
            {(selectedBucket?.total_count ?? 0) > 0 && (
              <VStack align="stretch" spacing={2}>
                {(selectedBucket?.tasks ?? []).map((task) => (
                  <Box
                    key={task.id}
                    borderWidth="1px"
                    borderColor="ui.border"
                    borderRadius="10px"
                    borderLeftWidth="4px"
                    borderLeftColor={taskAccentColor(task)}
                    bg={taskCardBackground(task)}
                    px={3}
                    py={2.5}
                  >
                    <HStack justify="space-between" align="start" gap={3}>
                      <Box minW={0}>
                        <Text
                          as={task.closed_at ? "s" : undefined}
                          fontWeight="700"
                          noOfLines={1}
                        >
                          <Text
                            as="button"
                            onClick={() => {
                              dayDrawer.onClose()
                              navigate({
                                to: "/tasks",
                                search: { taskId: String(task.id) } as never,
                              })
                            }}
                            textDecoration="underline"
                            _hover={{ color: "ui.main" }}
                            textAlign="left"
                          >
                            {task.title}
                          </Text>
                        </Text>
                        <Text fontSize="sm" color="ui.muted" noOfLines={1}>
                          {task.project_name || `Проект #${task.project_id}`} •{" "}
                          {task.assignee_name || "Без исполнителя"}
                        </Text>
                      </Box>
                      <VStack spacing={1} align="end">
                        <Badge
                          borderRadius="full"
                          bg={taskAccentColor(task)}
                          color="white"
                        >
                          {taskDeadlineLabel(task)}
                        </Badge>
                        <Badge borderRadius="full">
                          {task.status_name || "Без статуса"}
                        </Badge>
                      </VStack>
                    </HStack>
                    <Text fontSize="xs" color="ui.darkSlate" mt={1}>
                      Срок: {new Date(task.due_date).toLocaleString("ru-RU")}
                    </Text>
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

function shiftDate(current: Date, mode: CalendarViewMode, direction: -1 | 1): Date {
  const next = new Date(current)
  if (mode === "day") {
    next.setDate(next.getDate() + direction)
    return next
  }
  if (mode === "week") {
    next.setDate(next.getDate() + direction * 7)
    return next
  }
  if (mode === "year") {
    return new Date(next.getFullYear() + direction, 0, 1)
  }
  return new Date(next.getFullYear(), next.getMonth() + direction, 1)
}

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1)
}

function calendarCellColor(bucket?: CalendarViewBucket): string {
  if (!bucket?.total_count) return "#FFFFFF"
  if (bucket.overdue_count > 0) return "#FDECEC"
  return "#F4FBF5"
}

function taskRowColor(task: {
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

function taskAccentColor(task: CalendarDayTask): string {
  if (task.closed_at && task.closed_overdue) return "#C62828"
  if (task.closed_at) return "#6b7280"
  if (task.is_overdue || task.computed_deadline_state === "red") return "#C62828"
  if (task.computed_deadline_state === "yellow") return "#B7791F"
  return "#2F855A"
}

function taskCardBackground(task: CalendarDayTask): string {
  if (task.closed_at) return "#F7F8FA"
  if (task.is_overdue || task.computed_deadline_state === "red") return "#FFF4F4"
  if (task.computed_deadline_state === "yellow") return "#FFF8E8"
  return "#F3FBF5"
}

function taskDeadlineLabel(task: CalendarDayTask): string {
  if (task.closed_at && task.closed_overdue) return "Закрыта с просрочкой"
  if (task.closed_at) return "Закрыта"
  if (task.is_overdue || task.computed_deadline_state === "red") return "Просрочено"
  if (task.computed_deadline_state === "yellow") return "Критично"
  return "В срок"
}
