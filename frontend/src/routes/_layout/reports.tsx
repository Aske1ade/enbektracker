import {
  Box,
  Button,
  Checkbox,
  Collapse,
  Container,
  FormControl,
  FormLabel,
  Grid,
  GridItem,
  HStack,
  Heading,
  Input,
  Select,
  Stack,
  Stat,
  StatLabel,
  StatNumber,
  Switch,
  Table,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tr,
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { type ReactNode, useEffect, useMemo, useState } from "react"
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import useCustomToast from "../../hooks/useCustomToast"
import { trackerApi } from "../../services/trackerApi"
import type { ReportTaskRow } from "../../types/tracker"

export const Route = createFileRoute("/_layout/reports")({
  component: ReportsPage,
})

type ReportColumnKey =
  | "task_id"
  | "title"
  | "project_name"
  | "department_name"
  | "assignee_name"
  | "status_name"
  | "due_date"
  | "is_overdue"
  | "closed_at"
  | "closed_overdue"
  | "days_overdue"

type ReportColumnDef = {
  key: ReportColumnKey
  label: string
  defaultWidth: number
}

const REPORT_TEMPLATE_CUSTOM_KEY = "tracker.reports.custom-template.v1"
const REPORT_COLUMNS: ReportColumnDef[] = [
  { key: "task_id", label: "ID задачи", defaultWidth: 10 },
  { key: "title", label: "Наименование задачи", defaultWidth: 40 },
  { key: "project_name", label: "Проект", defaultWidth: 26 },
  { key: "department_name", label: "Департамент", defaultWidth: 24 },
  { key: "assignee_name", label: "Исполнитель", defaultWidth: 24 },
  { key: "status_name", label: "Состояние", defaultWidth: 18 },
  { key: "due_date", label: "Срок", defaultWidth: 20 },
  { key: "is_overdue", label: "Просрочено", defaultWidth: 12 },
  { key: "closed_at", label: "Закрыта", defaultWidth: 20 },
  { key: "closed_overdue", label: "Закрыта с просрочкой", defaultWidth: 18 },
  { key: "days_overdue", label: "Дней просрочки", defaultWidth: 14 },
]

const FULL_COLUMNS: ReportColumnKey[] = [
  "task_id",
  "title",
  "project_name",
  "department_name",
  "assignee_name",
  "status_name",
  "due_date",
  "is_overdue",
  "closed_at",
  "closed_overdue",
  "days_overdue",
]

const COMPACT_COLUMNS: ReportColumnKey[] = [
  "title",
  "project_name",
  "assignee_name",
  "department_name",
  "status_name",
  "due_date",
  "is_overdue",
  "closed_at",
]

function ReportsPage() {
  const showToast = useCustomToast()
  const [exportTemplate, setExportTemplate] = useState<
    "full" | "compact" | "custom"
  >("full")
  const [selectedColumns, setSelectedColumns] = useState<ReportColumnKey[]>(
    FULL_COLUMNS,
  )
  const [columnWidths, setColumnWidths] = useState<Record<string, number>>({})
  const [dateFrom, setDateFrom] = useState("")
  const [dateTo, setDateTo] = useState("")
  const [projectId, setProjectId] = useState("")
  const [departmentId, setDepartmentId] = useState("")
  const [assigneeId, setAssigneeId] = useState("")
  const [statusId, setStatusId] = useState("")
  const [overdueOnly, setOverdueOnly] = useState(false)
  const [isDownloading, setIsDownloading] = useState<null | "csv" | "xlsx">(
    null,
  )
  const [previewPage, setPreviewPage] = useState(1)
  const [previewPageSize, setPreviewPageSize] = useState(20)
  const [showFilters, setShowFilters] = useState(false)

  const { data: projectsData } = useQuery({
    queryKey: ["projects-for-reports"],
    queryFn: () =>
      trackerApi.listProjects({
        page: 1,
        page_size: 200,
        sort_by: "name",
        sort_order: "asc",
      }),
  })

  const { data: departmentsData } = useQuery({
    queryKey: ["departments-for-reports"],
    queryFn: () => trackerApi.listDepartments(),
  })

  const { data: usersData } = useQuery({
    queryKey: ["tracker-users"],
    queryFn: () => trackerApi.listUsers(),
    retry: false,
  })

  const projectNumber = projectId ? Number(projectId) : undefined

  useEffect(() => {
    if (exportTemplate === "full") {
      setSelectedColumns(FULL_COLUMNS)
    } else if (exportTemplate === "compact") {
      setSelectedColumns(COMPACT_COLUMNS)
    }
  }, [exportTemplate])

  useEffect(() => {
    try {
      const raw = localStorage.getItem(REPORT_TEMPLATE_CUSTOM_KEY)
      if (!raw) return
      const parsed = JSON.parse(raw) as {
        columns?: ReportColumnKey[]
        widths?: Record<string, number>
      }
      if (parsed.columns?.length) {
        setSelectedColumns(
          parsed.columns.filter((key) =>
            REPORT_COLUMNS.some((column) => column.key === key),
          ),
        )
        setExportTemplate("custom")
      }
      if (parsed.widths) {
        setColumnWidths(parsed.widths)
      }
    } catch {
      // ignore invalid cached template
    }
  }, [])

  const selectedColumnDefs = useMemo(
    () =>
      selectedColumns
        .map((key) => REPORT_COLUMNS.find((column) => column.key === key))
        .filter((column): column is ReportColumnDef => Boolean(column)),
    [selectedColumns],
  )

  const columnsParam = useMemo(
    () => selectedColumns.join(","),
    [selectedColumns],
  )

  const columnWidthsParam = useMemo(
    () =>
      selectedColumns
        .map((key) =>
          String(
            Math.max(
              8,
              Math.min(
                80,
                Number(
                  columnWidths[key] ??
                    REPORT_COLUMNS.find((column) => column.key === key)
                      ?.defaultWidth ??
                    20,
                ),
              ),
            ),
          ),
        )
        .join(","),
    [columnWidths, selectedColumns],
  )
  const exportTemplateApi: "full" | "compact" =
    exportTemplate === "compact" ? "compact" : "full"

  const { data: statusesData } = useQuery({
    queryKey: ["report-statuses", projectNumber],
    queryFn: () =>
      projectNumber
        ? trackerApi.getProjectStatuses(projectNumber)
        : trackerApi.getProjectStatuses(undefined, { catalog: true }),
  })

  const params = useMemo(
    () => ({
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      project_id: projectId ? Number(projectId) : undefined,
      department_id: departmentId ? Number(departmentId) : undefined,
      assignee_id: assigneeId ? Number(assigneeId) : undefined,
      workflow_status_id: statusId ? Number(statusId) : undefined,
      overdue_only: overdueOnly || undefined,
      template: exportTemplateApi,
      columns: columnsParam || undefined,
      column_widths: columnWidthsParam || undefined,
    }),
    [
      assigneeId,
      dateFrom,
      dateTo,
      departmentId,
      overdueOnly,
      projectId,
      statusId,
      exportTemplateApi,
      columnsParam,
      columnWidthsParam,
    ],
  )

  const { data: rows = [] } = useQuery({
    queryKey: ["reports-tasks", params],
    queryFn: () => trackerApi.reportTasks(params),
  })

  const pagedRows = useMemo(() => {
    const from = (previewPage - 1) * previewPageSize
    return rows.slice(from, from + previewPageSize)
  }, [rows, previewPage, previewPageSize])

  const totalPages = Math.max(1, Math.ceil(rows.length / previewPageSize))

  const tasksByDepartment = useMemo(
    () => aggregateRows(rows, "department_name").slice(0, 12),
    [rows],
  )
  const tasksByProject = useMemo(
    () => aggregateRows(rows, "project_name").slice(0, 12),
    [rows],
  )
  const tasksByStatus = useMemo(() => {
    const map = new Map<string, number>()
    for (const row of rows) {
      const statusName = row.status_name || "Без статуса"
      map.set(statusName, (map.get(statusName) ?? 0) + 1)
    }
    return [...map.entries()]
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count)
  }, [rows])

  const tasksByAssignee = useMemo(() => {
    const map = new Map<string, number>()
    for (const row of rows) {
      const assignee = row.assignee_name || "Не назначен"
      map.set(assignee, (map.get(assignee) ?? 0) + 1)
    }
    return [...map.entries()]
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 12)
  }, [rows])

  const tasksByDeadlineState = useMemo(() => {
    const now = new Date()
    const totals = {
      green: 0,
      yellow: 0,
      red: 0,
    }

    for (const row of rows) {
      if (row.is_overdue) {
        totals.red += 1
        continue
      }

      const due = new Date(row.due_date)
      const diffDays = Math.ceil(
        (due.getTime() - now.getTime()) / (1000 * 60 * 60 * 24),
      )

      if (diffDays <= 2) {
        totals.yellow += 1
      } else {
        totals.green += 1
      }
    }

    return [
      { name: "В срок", count: totals.green, color: "#2E7D32" },
      { name: "Критично", count: totals.yellow, color: "#F9A825" },
      { name: "Просрочено", count: totals.red, color: "#C62828" },
    ]
  }, [rows])

  const downloadReport = async (kind: "csv" | "xlsx") => {
    try {
      setIsDownloading(kind)
      const token = localStorage.getItem("access_token") || ""
      const url =
        kind === "csv"
          ? trackerApi.reportCsvUrl(params)
          : trackerApi.reportXlsxUrl(params)
      const response = await fetch(url, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      if (!response.ok) {
        const text = await response.text()
        throw new Error(text || `Ошибка экспорта (${response.status})`)
      }
      const blob = await response.blob()
      const objectUrl = URL.createObjectURL(blob)
      const anchor = document.createElement("a")
      anchor.href = objectUrl
      anchor.download =
        kind === "csv" ? "tasks-report.csv" : "tasks-report.xlsx"
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(objectUrl)
      showToast.success("Успешно", `Отчёт ${kind.toUpperCase()} выгружен`)
    } catch (error) {
      showToast.error("Не удалось выгрузить отчёт", error)
    } finally {
      setIsDownloading(null)
    }
  }

  const toggleColumn = (columnKey: ReportColumnKey, enabled: boolean) => {
    setSelectedColumns((prev) => {
      if (enabled) {
        if (prev.includes(columnKey)) return prev
        return [...prev, columnKey]
      }
      if (prev.length <= 1) return prev
      return prev.filter((key) => key !== columnKey)
    })
    setExportTemplate("custom")
  }

  const saveCustomTemplate = () => {
    localStorage.setItem(
      REPORT_TEMPLATE_CUSTOM_KEY,
      JSON.stringify({
        columns: selectedColumns,
        widths: columnWidths,
      }),
    )
    setExportTemplate("custom")
    showToast.success("Успешно", "Пользовательский шаблон сохранен")
  }

  return (
    <Container maxW="full" py={6} overflowX="hidden">
      <Stack
        mb={5}
        spacing={3}
        direction={{ base: "column", md: "row" }}
        justify="space-between"
      >
        <HStack spacing={3} minW={0}>
          <Box
            as="img"
            src="/assets/images/favicon.png"
            alt="Enbek Tracker"
            w="30px"
            h="30px"
            borderRadius="md"
          />
          <Heading size="lg">Отчёты</Heading>
        </HStack>
        <Button
          size="sm"
          variant="subtle"
          alignSelf={{ base: "start", md: "center" }}
          onClick={() => setShowFilters((prev) => !prev)}
        >
          {showFilters ? "Скрыть фильтры" : "Показать фильтры"}
        </Button>
      </Stack>

      <Box
        position="sticky"
        top="8px"
        zIndex={4}
        borderWidth="1px"
        borderColor="ui.border"
        borderRadius="12px"
        bg="white"
        boxShadow="sm"
        px={4}
        py={3}
        mb={4}
      >
        <HStack justify="space-between" flexWrap="wrap" gap={3} minW={0}>
          <Text fontSize="sm" color="ui.muted" minW={0}>
            Записей в отчёте: {rows.length}
          </Text>
          <HStack spacing={2} flexWrap="wrap">
            <Button
              size="sm"
              onClick={() => downloadReport("csv")}
              isLoading={isDownloading === "csv"}
            >
              Экспорт CSV
            </Button>
            <Button
              size="sm"
              variant="primary"
              onClick={() => downloadReport("xlsx")}
              isLoading={isDownloading === "xlsx"}
            >
              Экспорт XLSX
            </Button>
          </HStack>
        </HStack>
      </Box>

      <Grid templateColumns="1fr" gap={4} minW={0}>
        <GridItem minW={0}>
          <Collapse in={showFilters} animateOpacity>
            <Box
              borderWidth="1px"
              borderColor="ui.border"
              borderRadius="12px"
              p={4}
              bg="white"
              boxShadow="sm"
            >
            <HStack justify="space-between" mb={3} flexWrap="wrap">
              <HStack spacing={3}>
                <Box
                  as="img"
                  src="/assets/images/favicon.png"
                  alt="Enbek Tracker"
                  w="24px"
                  h="24px"
                  borderRadius="sm"
                />
                <Heading size="sm">Фильтры и шаблон отчёта</Heading>
              </HStack>
              <HStack spacing={2}>
                <FormControl w={{ base: "100%", md: "220px" }}>
                  <FormLabel mb={1}>Шаблон</FormLabel>
                  <Select
                    value={exportTemplate}
                    onChange={(e) =>
                      setExportTemplate(
                        e.target.value as "full" | "compact" | "custom",
                      )
                    }
                  >
                    <option value="full">Полный</option>
                    <option value="compact">Компактный</option>
                    <option value="custom">Пользовательский</option>
                  </Select>
                </FormControl>
              </HStack>
            </HStack>

            <Box
              borderWidth="1px"
              borderColor="ui.border"
              borderRadius="10px"
              p={3}
              mb={3}
              bg="#FAFCFF"
            >
              <HStack justify="space-between" mb={2} flexWrap="wrap" gap={2}>
                <Text fontWeight="600" fontSize="sm">
                  Колонки и ширины для выгрузки
                </Text>
                <Button size="xs" variant="subtle" onClick={saveCustomTemplate}>
                  Сохранить шаблон
                </Button>
              </HStack>
              <Grid templateColumns={{ base: "1fr", md: "repeat(2, 1fr)", xl: "repeat(3, 1fr)" }} gap={2}>
                {REPORT_COLUMNS.map((column) => {
                  const checked = selectedColumns.includes(column.key)
                  return (
                    <HStack
                      key={column.key}
                      borderWidth="1px"
                      borderColor="ui.border"
                      borderRadius="8px"
                      p={2}
                      justify="space-between"
                      align="center"
                      bg="white"
                    >
                      <Checkbox
                        isChecked={checked}
                        onChange={(e) =>
                          toggleColumn(column.key, e.target.checked)
                        }
                      >
                        <Text fontSize="sm">{column.label}</Text>
                      </Checkbox>
                      <Input
                        type="number"
                        size="xs"
                        w="78px"
                        min={8}
                        max={80}
                        value={
                          columnWidths[column.key] ?? column.defaultWidth
                        }
                        onChange={(e) =>
                          setColumnWidths((prev) => ({
                            ...prev,
                            [column.key]: Number(e.target.value || column.defaultWidth),
                          }))
                        }
                        isDisabled={!checked}
                      />
                    </HStack>
                  )
                })}
              </Grid>
            </Box>

            <Grid
              templateColumns={{ base: "1fr", md: "repeat(3, 1fr)", xl: "repeat(6, 1fr)" }}
              gap={3}
            >
              <VFilter label="С даты">
                <Input
                  type="date"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                />
              </VFilter>
              <VFilter label="По дату">
                <Input
                  type="date"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                />
              </VFilter>
              <VFilter label="Проект">
                <Select
                  value={projectId}
                  onChange={(e) => {
                    setProjectId(e.target.value)
                    setStatusId("")
                  }}
                >
                  <option value="">Все</option>
                  {projectsData?.data.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.name}
                    </option>
                  ))}
                </Select>
              </VFilter>
              <VFilter label="Департамент">
                <Select
                  value={departmentId}
                  onChange={(e) => setDepartmentId(e.target.value)}
                >
                  <option value="">Все</option>
                  {departmentsData?.data.map((department) => (
                    <option key={department.id} value={department.id}>
                      {department.name}
                    </option>
                  ))}
                </Select>
              </VFilter>
              <VFilter label="Исполнитель">
                <Select
                  value={assigneeId}
                  onChange={(e) => setAssigneeId(e.target.value)}
                >
                  <option value="">Все</option>
                  {usersData?.data.map((user) => (
                    <option key={user.id} value={user.id}>
                      {`${user.full_name || user.email} (#${user.id})`}
                    </option>
                  ))}
                </Select>
              </VFilter>
              <VFilter label="Состояние задачи">
                <Select
                  value={statusId}
                  onChange={(e) => setStatusId(e.target.value)}
                >
                  <option value="">Все</option>
                  {statusesData?.data.map((status) => (
                    <option key={status.id} value={status.id}>
                      {status.name}
                    </option>
                  ))}
                </Select>
              </VFilter>
            </Grid>

            <HStack mt={3} justify="space-between" flexWrap="wrap" gap={3}>
              <FormControl maxW="280px">
                <FormLabel mb={1}>Только просроченные</FormLabel>
                <Switch
                  isChecked={overdueOnly}
                  onChange={(e) => setOverdueOnly(e.target.checked)}
                />
              </FormControl>
            </HStack>
            </Box>
          </Collapse>
        </GridItem>

        <GridItem minW={0}>
          <Box
            borderWidth="1px"
            borderColor="ui.border"
            borderRadius="12px"
            overflow="hidden"
            bg="white"
            boxShadow="sm"
            mb={4}
          >
            <Box p={3} borderBottomWidth="1px" bg="gray.50">
              <HStack justify="space-between" flexWrap="wrap" gap={2}>
                <Text fontWeight="600">Таблица задач (preview)</Text>
                <HStack>
                  <Select
                    size="sm"
                    value={previewPageSize}
                    onChange={(e) => {
                      setPreviewPageSize(Number(e.target.value))
                      setPreviewPage(1)
                    }}
                    w="120px"
                  >
                    {[20, 50, 100].map((size) => (
                      <option key={size} value={size}>
                        {size} / стр.
                      </option>
                    ))}
                  </Select>
                  <Button
                    size="sm"
                    onClick={() => setPreviewPage((p) => Math.max(1, p - 1))}
                  >
                    Назад
                  </Button>
                  <Text fontSize="sm">
                    {previewPage}/{totalPages}
                  </Text>
                  <Button
                    size="sm"
                    onClick={() =>
                      setPreviewPage((p) => Math.min(totalPages, p + 1))
                    }
                  >
                    Вперёд
                  </Button>
                </HStack>
              </HStack>
            </Box>

            <Box overflowX="auto" maxW="100%">
              <Table size="sm">
                <Thead>
                  <Tr>
                    {selectedColumnDefs.map((column) => (
                      <Th key={column.key} minW={`${column.defaultWidth}ch`}>
                        {column.label}
                      </Th>
                    ))}
                  </Tr>
                </Thead>
                <Tbody>
                  {pagedRows.map((row) => (
                    <Tr key={`${row.task_id}-${row.due_date}`}>
                      {selectedColumnDefs.map((column) => (
                        <Td
                          key={`${row.task_id}-${column.key}`}
                          minW={`${Math.max(
                            8,
                            Math.min(
                              80,
                              Number(
                                columnWidths[column.key] ?? column.defaultWidth,
                              ),
                            ),
                          )}ch`}
                        >
                          {renderReportColumnValue(row, column.key)}
                        </Td>
                      ))}
                    </Tr>
                  ))}
                </Tbody>
              </Table>
            </Box>
          </Box>

          <Grid
            templateColumns={{ base: "1fr", md: "repeat(3, 1fr)" }}
            gap={3}
            mb={4}
          >
            <Stat
              borderWidth="1px"
              borderColor="ui.border"
              borderRadius="12px"
              p={3}
              bg="white"
              boxShadow="sm"
            >
              <StatLabel>Всего задач в выборке</StatLabel>
              <StatNumber>{rows.length}</StatNumber>
            </Stat>
            <Stat
              borderWidth="1px"
              borderColor="ui.border"
              borderRadius="12px"
              p={3}
              bg="white"
              boxShadow="sm"
            >
              <StatLabel>Просроченных</StatLabel>
              <StatNumber>
                {rows.filter((row) => row.is_overdue).length}
              </StatNumber>
            </Stat>
            <Stat
              borderWidth="1px"
              borderColor="ui.border"
              borderRadius="12px"
              p={3}
              bg="white"
              boxShadow="sm"
            >
              <StatLabel>Проектов</StatLabel>
              <StatNumber>
                {new Set(rows.map((row) => row.project_name)).size}
              </StatNumber>
            </Stat>
          </Grid>

          <Grid templateColumns={{ base: "1fr", xl: "1fr 1fr" }} gap={4} mb={4} minW={0}>
            <ChartPanel title="Задачи по департаментам и срокам">
              <ChartBox>
                <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={300}>
                  <BarChart data={tasksByDepartment}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="name" hide />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Legend />
                    <Bar
                      dataKey="total"
                      name="Всего"
                      fill="#1E3A5F"
                      radius={[6, 6, 0, 0]}
                    />
                    <Bar
                      dataKey="overdue"
                      name="Просрочено"
                      fill="#C62828"
                      radius={[6, 6, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </ChartBox>
            </ChartPanel>

            <ChartPanel title="Объем задач по проектам">
              <ChartBox>
                <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={300}>
                  <BarChart data={tasksByProject}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="name" hide />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Legend />
                    <Bar
                      dataKey="total"
                      name="Всего"
                      fill="#2A76D2"
                      radius={[6, 6, 0, 0]}
                    />
                    <Bar
                      dataKey="overdue"
                      name="Просрочено"
                      fill="#F97316"
                      radius={[6, 6, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </ChartBox>
            </ChartPanel>
          </Grid>

          <Grid templateColumns={{ base: "1fr", xl: "1fr 1fr" }} gap={4} mb={4} minW={0}>
            <ChartPanel title="Распределение задач по состоянию">
              <ChartBox>
                <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={300}>
                  <PieChart>
                    <Tooltip />
                    <Legend />
                    <Pie
                      data={tasksByStatus}
                      dataKey="count"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={102}
                      label
                    >
                      {tasksByStatus.map((entry, index) => (
                        <Cell
                          key={`${entry.name}-${index}`}
                          fill={pieColors[index % pieColors.length]}
                        />
                      ))}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
              </ChartBox>
            </ChartPanel>

            <ChartPanel title="Распределение задач по срокам">
              <ChartBox>
                <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={300}>
                  <PieChart>
                    <Tooltip />
                    <Legend />
                    <Pie
                      data={tasksByDeadlineState}
                      dataKey="count"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={102}
                      label
                    >
                      {tasksByDeadlineState.map((entry) => (
                        <Cell key={entry.name} fill={entry.color} />
                      ))}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
              </ChartBox>
            </ChartPanel>
          </Grid>

          <Grid templateColumns={{ base: "1fr", xl: "1fr" }} gap={4} mb={4} minW={0}>
            <ChartPanel title="Распределение задач по исполнителям">
              <ChartBox h="320px">
                <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={320}>
                  <BarChart
                    data={tasksByAssignee}
                    layout="vertical"
                    margin={{ left: 8 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis type="number" allowDecimals={false} />
                    <YAxis type="category" dataKey="name" width={170} />
                    <Tooltip />
                    <Bar
                      dataKey="count"
                      name="Задач"
                      fill="#2F855A"
                      radius={[0, 6, 6, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </ChartBox>
            </ChartPanel>
          </Grid>

        </GridItem>
      </Grid>
    </Container>
  )
}

function VFilter({ label, children }: { label: string; children: ReactNode }) {
  return (
    <FormControl mb={3}>
      <FormLabel>{label}</FormLabel>
      {children}
    </FormControl>
  )
}

function ChartPanel({
  title,
  children,
}: { title: string; children: ReactNode }) {
  return (
    <Box
      minW={0}
      overflow="hidden"
      borderWidth="1px"
      borderColor="ui.border"
      borderRadius="12px"
      p={4}
      bg="white"
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

function ChartBox({
  children,
  h = "300px",
}: {
  children: ReactNode
  h?: string
}) {
  return (
    <Box minW={0} w="100%" h={h}>
      {children}
    </Box>
  )
}

function renderReportColumnValue(row: ReportTaskRow, key: ReportColumnKey): string {
  if (key === "task_id") return String(row.task_id)
  if (key === "title") return row.title
  if (key === "project_name") return row.project_name || "-"
  if (key === "department_name") return row.department_name || "-"
  if (key === "assignee_name") return row.assignee_name || "-"
  if (key === "status_name") return row.status_name || "-"
  if (key === "due_date") return new Date(row.due_date).toLocaleString("ru-RU")
  if (key === "is_overdue") return row.is_overdue ? "Да" : "Нет"
  if (key === "closed_at") return row.closed_at ? new Date(row.closed_at).toLocaleString("ru-RU") : "-"
  if (key === "closed_overdue") return row.closed_overdue ? "Да" : "Нет"
  if (key === "days_overdue") return String(row.days_overdue ?? 0)
  return "-"
}

function aggregateRows(
  rows: ReportTaskRow[],
  key: "project_name" | "department_name",
): Array<{ name: string; total: number; overdue: number }> {
  const map = new Map<
    string,
    { name: string; total: number; overdue: number }
  >()
  for (const row of rows) {
    const groupName =
      key === "project_name"
        ? row.project_name || "Без проекта"
        : row.department_name || "Без департамента"

    const current = map.get(groupName) ?? {
      name: groupName,
      total: 0,
      overdue: 0,
    }

    current.total += 1
    if (row.is_overdue) {
      current.overdue += 1
    }

    map.set(groupName, current)
  }

  return [...map.values()].sort((a, b) => b.total - a.total)
}

const pieColors = [
  "#1E3A5F",
  "#2E7D32",
  "#F9A825",
  "#C62828",
  "#0D9488",
  "#7C3AED",
  "#6D4C41",
]
