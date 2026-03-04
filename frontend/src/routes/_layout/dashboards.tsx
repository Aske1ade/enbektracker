import {
  Box,
  Button,
  Container,
  FormControl,
  FormLabel,
  Grid,
  GridItem,
  HStack,
  Heading,
  IconButton,
  Select,
  Stat,
  StatHelpText,
  StatLabel,
  StatNumber,
  Text,
  VStack,
  useColorModeValue,
} from "@chakra-ui/react"
import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useMemo, useState } from "react"
import { FiSettings } from "react-icons/fi"
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  PolarAngleAxis,
  RadialBar,
  RadialBarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { trackerApi } from "../../services/trackerApi"

export const Route = createFileRoute("/_layout/dashboards")({
  component: DashboardsPage,
})

function DashboardsPage() {
  const [topLimit, setTopLimit] = useState<5 | 10>(5)
  const [showScopeSettings, setShowScopeSettings] = useState(false)
  const [scopeTarget, setScopeTarget] = useState<"all" | "group" | "project">("all")
  const [scopeGroupId, setScopeGroupId] = useState("")
  const [scopeProjectId, setScopeProjectId] = useState("")
  const [showRegularAdvanced, setShowRegularAdvanced] = useState(false)
  const [showStatusDistribution, setShowStatusDistribution] = useState(false)
  const sectionTitleColor = useColorModeValue("ui.darkSlate", "ui.light")
  const subtitleColor = useColorModeValue("gray.600", "ui.muted")

  const { data: currentUser } = useQuery({
    queryKey: ["currentUser"],
    queryFn: () => trackerApi.getCurrentUser(),
    retry: false,
  })

  const dashboardProjectId =
    scopeTarget === "project" && scopeProjectId
      ? Number(scopeProjectId)
      : undefined
  const dashboardDepartmentId =
    scopeTarget === "group" && scopeGroupId
      ? Number(scopeGroupId)
      : undefined

  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: [
      "dashboard-summary",
      topLimit,
      scopeTarget,
      scopeGroupId,
      scopeProjectId,
    ],
    queryFn: () =>
      trackerApi.dashboardSummary({
        top_limit: topLimit,
        scope_mode: "managed",
        project_id: dashboardProjectId,
        department_id: dashboardDepartmentId,
      }),
    placeholderData: keepPreviousData,
    refetchInterval: 30_000,
    refetchIntervalInBackground: true,
  })

  const { data: distributions, isLoading: distributionsLoading } = useQuery({
    queryKey: [
      "dashboard-distributions",
      scopeTarget,
      scopeGroupId,
      scopeProjectId,
    ],
    queryFn: () =>
      trackerApi.dashboardDistributions({
        scope_mode: "managed",
        project_id: dashboardProjectId,
        department_id: dashboardDepartmentId,
      }),
    placeholderData: keepPreviousData,
    refetchInterval: 30_000,
    refetchIntervalInBackground: true,
  })

  const canUseExtendedScope = Boolean(summary?.can_use_extended_scope)

  const { data: scopeProjectsData } = useQuery({
    queryKey: ["dashboard-scope-projects"],
    queryFn: () =>
      trackerApi.listProjects({
        page: 1,
        page_size: 1000,
        sort_by: "name",
        sort_order: "asc",
      }),
    enabled: canUseExtendedScope,
    staleTime: 5 * 60_000,
  })

  const scopeProjects = useMemo(
    () => (scopeProjectsData?.data ?? []).filter((project) => Boolean(project.id)),
    [scopeProjectsData?.data],
  )
  const scopeGroups = useMemo(() => {
    const groupsMap = new Map<number, string>()
    for (const project of scopeProjects) {
      if (!project.department_id || !project.department_name) continue
      if (!groupsMap.has(project.department_id)) {
        groupsMap.set(project.department_id, project.department_name)
      }
    }
    return Array.from(groupsMap.entries())
      .map(([id, name]) => ({ id, name }))
      .sort((a, b) => a.name.localeCompare(b.name, "ru"))
  }, [scopeProjects])

  const scopeLabel = useMemo(() => {
    if (!canUseExtendedScope) return "Личный режим"
    if (scopeTarget === "project") {
      const project = scopeProjects.find((item) => item.id === Number(scopeProjectId))
      return project ? `Проект: ${project.name}` : "Фильтр: проект не выбран"
    }
    if (scopeTarget === "group") {
      const group = scopeGroups.find((item) => item.id === Number(scopeGroupId))
      return group ? `Группа: ${group.name}` : "Фильтр: группа не выбрана"
    }
    return "Весь блок / доступные проекты"
  }, [canUseExtendedScope, scopeTarget, scopeProjectId, scopeProjects, scopeGroupId, scopeGroups])

  const isRegularOnly = Boolean(currentUser) && !canUseExtendedScope
  const showExtendedPanels = canUseExtendedScope || showRegularAdvanced

  const deadlineInTimeCount = summary?.deadline_in_time_count ?? 0
  const overdueCount = summary?.deadline_overdue_count ?? 0

  const departmentsBars = distributions?.departments ?? []
  const statusPie = useMemo(
    () => (distributions?.statuses ?? []).filter((item) => item.count > 0),
    [distributions?.statuses],
  )

  const topExecutorsPie = useMemo(
    () => (summary?.top_executors ?? []).filter((item) => item.count > 0),
    [summary?.top_executors],
  )
  const topOverdueExecutorsPie = useMemo(
    () =>
      (summary?.top_overdue_executors ?? []).filter((item) => item.count > 0),
    [summary?.top_overdue_executors],
  )

  const closedInTimePercent = useMemo(() => {
    const closed =
      (summary?.closed_in_time_count ?? 0) +
      (summary?.closed_overdue_count ?? 0)
    if (!closed) return 0
    return Math.round(((summary?.closed_in_time_count ?? 0) / closed) * 100)
  }, [summary])
  const closedOverduePercent = useMemo(() => {
    const closed =
      (summary?.closed_in_time_count ?? 0) +
      (summary?.closed_overdue_count ?? 0)
    if (!closed) return 0
    return 100 - closedInTimePercent
  }, [closedInTimePercent, summary])

  return (
    <Container maxW="full" py={6}>
      <Heading size="lg" mb={1}>
        Дашборды
      </Heading>
      <Text color={subtitleColor} mb={5}>
        Сводка по задачам, распределения и ключевые показатели исполнения
      </Text>

      <HStack justify="space-between" mb={4} flexWrap="wrap" gap={2}>
        {canUseExtendedScope ? (
          <HStack>
            <IconButton
              aria-label="Настройки фильтра дашборда"
              icon={<FiSettings />}
              size="sm"
              variant="subtle"
              onClick={() => setShowScopeSettings((prev) => !prev)}
            />
            <Text fontSize="sm" color="ui.muted">
              {scopeLabel}
            </Text>
          </HStack>
        ) : (
          <Button
            size="sm"
            variant="subtle"
            onClick={() => setShowRegularAdvanced((prev) => !prev)}
          >
            {showRegularAdvanced
              ? "Скрыть расширенную аналитику"
              : "Показать расширенную аналитику"}
          </Button>
        )}
      </HStack>
      {canUseExtendedScope && showScopeSettings ? (
        <Box
          borderWidth="1px"
          borderColor="ui.border"
          borderRadius="10px"
          p={3}
          mb={4}
        >
          <VStack align="stretch" spacing={3}>
            <FormControl>
              <FormLabel mb={1}>Режим выборки</FormLabel>
              <Select
                size="sm"
                value={scopeTarget}
                onChange={(event) => {
                  const nextTarget = event.target.value as "all" | "group" | "project"
                  setScopeTarget(nextTarget)
                  if (nextTarget !== "group") setScopeGroupId("")
                  if (nextTarget !== "project") setScopeProjectId("")
                }}
              >
                <option value="all">Весь блок / доступные проекты</option>
                <option value="group">Конкретная группа</option>
                <option value="project">Конкретный проект</option>
              </Select>
            </FormControl>
            {scopeTarget === "group" ? (
              <FormControl>
                <FormLabel mb={1}>Группа</FormLabel>
                <Select
                  size="sm"
                  value={scopeGroupId}
                  onChange={(event) => setScopeGroupId(event.target.value)}
                >
                  <option value="">Выберите группу</option>
                  {scopeGroups.map((group) => (
                    <option key={`dashboard-group-${group.id}`} value={group.id}>
                      {group.name}
                    </option>
                  ))}
                </Select>
              </FormControl>
            ) : null}
            {scopeTarget === "project" ? (
              <FormControl>
                <FormLabel mb={1}>Проект</FormLabel>
                <Select
                  size="sm"
                  value={scopeProjectId}
                  onChange={(event) => setScopeProjectId(event.target.value)}
                >
                  <option value="">Выберите проект</option>
                  {scopeProjects.map((project) => (
                    <option key={`dashboard-project-${project.id}`} value={project.id}>
                      {project.name}
                    </option>
                  ))}
                </Select>
              </FormControl>
            ) : null}
          </VStack>
        </Box>
      ) : null}

      <Grid
        templateColumns={{ base: "1fr", md: "repeat(3, minmax(0, 1fr))" }}
        gap={4}
        mb={4}
      >
        <MetricCard
          label="Общее количество задач"
          value={summary?.total_tasks ?? 0}
          helpText="Только незавершённые задачи"
          isLoading={summaryLoading}
        />
        <MetricCard
          label="Задачи по сроку"
          value={deadlineInTimeCount}
          helpText="Незавершённые и не просроченные"
          color="#2F855A"
          isLoading={summaryLoading}
        />
        <MetricCard
          label="Просроченные задачи"
          value={overdueCount}
          helpText="Незавершённые просроченные"
          color="#C53030"
          isLoading={summaryLoading}
        />
      </Grid>

      <Grid templateColumns="1fr" gap={4} mb={4}>
        <GridItem minW={0}>
          <Panel title="Индикаторы закрытия">
            <ChartBox h="340px">
              <Grid templateColumns={{ base: "1fr", md: "1fr 1fr" }} gap={3} h="100%">
                <RadialIndicator
                  label="Закрыто в срок"
                  value={closedInTimePercent}
                  color="#2F855A"
                />
                <RadialIndicator
                  label="Закрыто с просрочкой"
                  value={closedOverduePercent}
                  color="#C53030"
                />
              </Grid>
            </ChartBox>
          </Panel>
        </GridItem>
      </Grid>

      {showExtendedPanels ? (
        <>
        <Box mb={4}>
          <HStack justify="space-between" mb={2}>
            <Text fontWeight="600" color={sectionTitleColor}>
              Распределение по состоянию задач
            </Text>
            <Button
              size="sm"
              variant="subtle"
              onClick={() => setShowStatusDistribution((prev) => !prev)}
            >
              {showStatusDistribution ? "Скрыть" : "Показать"}
            </Button>
          </HStack>
          {showStatusDistribution ? (
            <Panel title="Распределение по состоянию задач">
              <ChartBox h="340px">
                {distributionsLoading || !statusPie.length ? (
                  <CenterText text="Нет данных по состояниям" />
                ) : (
                  <ResponsiveContainer
                    width="100%"
                    height="100%"
                    minWidth={0}
                    minHeight={340}
                    debounce={40}
                  >
                    <PieChart>
                      <Tooltip />
                      <Legend />
                      <Pie
                        data={statusPie}
                        dataKey="count"
                        nameKey="status_name"
                        cx="50%"
                        cy="50%"
                        outerRadius={115}
                        label
                      >
                        {statusPie.map((entry, index) => (
                          <Cell
                            key={`${entry.status_code ?? entry.status_name}-${entry.status_id}`}
                            fill={chartColors[index % chartColors.length]}
                          />
                        ))}
                      </Pie>
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </ChartBox>
            </Panel>
          ) : null}
        </Box>

        <Grid templateColumns="1fr" gap={4} mb={4}>
          <GridItem minW={0}>
            <Panel title="Количество задач по департаментам">
              <ChartBox h="320px">
                {!departmentsBars.length ? (
                  <CenterText text="Нет данных по департаментам" />
                ) : (
                  <ResponsiveContainer
                    width="100%"
                    height="100%"
                    minWidth={0}
                    minHeight={320}
                    debounce={40}
                  >
                    <BarChart
                      data={departmentsBars}
                      layout="vertical"
                      margin={{ left: 16, right: 8 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis type="number" allowDecimals={false} />
                      <YAxis
                        type="category"
                        dataKey="department_name"
                        width={170}
                      />
                      <Tooltip />
                      <Bar dataKey="count" name="Задач" radius={[0, 6, 6, 0]}>
                        {departmentsBars.map((entry, index) => (
                          <Cell
                            key={`${entry.department_name}-${index}`}
                            fill={chartColors[index % chartColors.length]}
                            cursor="pointer"
                            onClick={() => {
                              if (!entry.department_id) return
                              openTasksWithFilters({
                                departmentId: entry.department_id,
                              })
                            }}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </ChartBox>
            </Panel>
          </GridItem>
        </Grid>

        <HStack justify="space-between" mb={2}>
          <Text fontWeight="600" color={sectionTitleColor}>
            Рейтинг исполнителей
          </Text>
          <HStack>
            <Text fontSize="sm" color="ui.muted">
              Показать
            </Text>
            <Select
              size="sm"
              w="110px"
              value={topLimit}
              onChange={(event) =>
                setTopLimit(Number(event.target.value) === 10 ? 10 : 5)
              }
            >
              <option value={5}>Топ 5</option>
              <option value={10}>Топ 10</option>
            </Select>
          </HStack>
        </HStack>

        <Grid templateColumns={{ base: "1fr", xl: "1fr 1fr" }} gap={4} mb={4}>
          <GridItem minW={0}>
            <Panel title={`ТОП исполнителей (${topLimit})`}>
              <ChartBox h="300px">
                {!topExecutorsPie.length ? (
                  <CenterText text="Нет активных исполнителей" />
                ) : (
                  <ResponsiveContainer
                    width="100%"
                    height="100%"
                    minWidth={0}
                    minHeight={300}
                    debounce={40}
                  >
                    <PieChart>
                      <Tooltip />
                      <Legend />
                      <Pie
                        data={topExecutorsPie}
                        dataKey="count"
                        nameKey="user_name"
                        cx="50%"
                        cy="50%"
                        outerRadius={108}
                        label
                      >
                        {topExecutorsPie.map((entry, index) => (
                          <Cell
                            key={`${entry.user_id}-${index}`}
                            fill={chartColors[index % chartColors.length]}
                            cursor="pointer"
                            onClick={() => {
                              openTasksWithFilters({ assigneeId: entry.user_id })
                            }}
                          />
                        ))}
                      </Pie>
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </ChartBox>
            </Panel>
          </GridItem>

          <GridItem minW={0}>
            <Panel title={`ТОП исполнителей по просроченным задачам (${topLimit})`}>
              <ChartBox h="300px">
                {!topOverdueExecutorsPie.length ? (
                  <CenterText text="Просроченных задач нет" />
                ) : (
                  <ResponsiveContainer
                    width="100%"
                    height="100%"
                    minWidth={0}
                    minHeight={300}
                    debounce={40}
                  >
                    <PieChart>
                      <Tooltip />
                      <Legend />
                      <Pie
                        data={topOverdueExecutorsPie}
                        dataKey="count"
                        nameKey="user_name"
                        cx="50%"
                        cy="50%"
                        outerRadius={108}
                        label
                      >
                        {topOverdueExecutorsPie.map((entry, index) => (
                          <Cell
                            key={`${entry.user_id}-${index}`}
                            fill={chartColors[(index + 3) % chartColors.length]}
                            cursor="pointer"
                            onClick={() => {
                              openTasksWithFilters({
                                assigneeId: entry.user_id,
                                overdueOnly: true,
                              })
                            }}
                          />
                        ))}
                      </Pie>
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </ChartBox>
            </Panel>
          </GridItem>
        </Grid>
        </>
      ) : null}

      {isRegularOnly && !showRegularAdvanced ? (
        <Text fontSize="sm" color="ui.muted">
          Для обычного пользователя расширенная аналитика скрыта по умолчанию.
        </Text>
      ) : null}

    </Container>
  )
}

function MetricCard({
  label,
  value,
  helpText,
  color,
  isLoading,
}: {
  label: string
  value: number
  helpText: string
  color?: string
  isLoading: boolean
}) {
  const cardBg = useColorModeValue("white", "#162235")
  return (
    <Box
      borderWidth="1px"
      borderColor="ui.border"
      borderRadius="10px"
      p={4}
      bg={cardBg}
      boxShadow="sm"
    >
      <Stat>
        <StatLabel>{label}</StatLabel>
        <StatNumber>{isLoading ? "..." : value}</StatNumber>
        <StatHelpText>{helpText}</StatHelpText>
      </Stat>
      {color ? <Box mt={2} h="4px" borderRadius="sm" bg={color} /> : null}
    </Box>
  )
}

function Panel({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  const panelBg = useColorModeValue("white", "#162235")
  return (
    <Box
      borderWidth="1px"
      borderColor="ui.border"
      borderRadius="10px"
      p={4}
      bg={panelBg}
      boxShadow="sm"
    >
      <Heading
        size="sm"
        mb={3}
        textTransform="uppercase"
        letterSpacing="0.04em"
      >
        {title}
      </Heading>
      {children}
    </Box>
  )
}

function ChartBox({ h, children }: { h: string; children: React.ReactNode }) {
  return (
    <Box minW={0} minH={h} w="100%" h={h}>
      {children}
    </Box>
  )
}

function CenterText({ text }: { text: string }) {
  return (
    <Box h="100%" display="flex" alignItems="center" justifyContent="center">
      <Text color="ui.muted">{text}</Text>
    </Box>
  )
}

const chartColors = [
  "#1E3A5F",
  "#2E7D32",
  "#F9A825",
  "#C62828",
  "#0D9488",
  "#6D4C41",
  "#7C3AED",
]

function RadialIndicator({
  label,
  value,
  color,
}: {
  label: string
  value: number
  color: string
}) {
  const labelColor = useColorModeValue("gray.600", "ui.muted")
  return (
    <Box position="relative" h="100%">
      <ResponsiveContainer
        width="100%"
        height="100%"
        minWidth={0}
        minHeight={220}
        debounce={40}
      >
        <RadialBarChart
          cx="50%"
          cy="50%"
          innerRadius="60%"
          outerRadius="92%"
          barSize={16}
          data={[{ name: label, value }]}
          startAngle={90}
          endAngle={-270}
        >
          <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
          <RadialBar dataKey="value" fill={color} cornerRadius={8} />
        </RadialBarChart>
      </ResponsiveContainer>
      <Box
        position="absolute"
        inset={0}
        display="flex"
        flexDirection="column"
        alignItems="center"
        justifyContent="center"
        pointerEvents="none"
      >
        <Text fontSize="2xl" fontWeight="700" lineHeight="1">
          {value}%
        </Text>
        <Text fontSize="xs" color={labelColor} mt={1} textAlign="center">
          {label}
        </Text>
      </Box>
    </Box>
  )
}

function openTasksWithFilters(params: {
  projectId?: number
  departmentId?: number
  assigneeId?: number
  overdueOnly?: boolean
}) {
  const query = new URLSearchParams()
  query.set("from", "dashboard")
  if (params.projectId) query.set("projectId", String(params.projectId))
  if (params.departmentId)
    query.set("departmentId", String(params.departmentId))
  if (params.assigneeId) query.set("assigneeId", String(params.assigneeId))
  if (params.overdueOnly) query.set("overdueOnly", "true")
  const search = query.toString()
  window.location.assign(`/tasks${search ? `?${search}` : ""}`)
}
