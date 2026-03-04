import {
  Box,
  Button,
  Container,
  Grid,
  GridItem,
  HStack,
  Heading,
  Stat,
  StatLabel,
  StatNumber,
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
import { useMemo, useState } from "react"

import useCustomToast from "../../hooks/useCustomToast"
import { trackerApi } from "../../services/trackerApi"

export const Route = createFileRoute("/_layout/discipline-help")({
  component: DisciplineHelpPage,
})

function DisciplineHelpPage() {
  const showToast = useCustomToast()
  const [downloading, setDownloading] = useState<null | "xlsx" | "docx">(null)

  const { data: summary } = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: () => trackerApi.dashboardSummary(),
  })

  const { data: disciplineData, isLoading } = useQuery({
    queryKey: ["discipline-help"],
    queryFn: () => trackerApi.reportDiscipline(),
  })

  const rows = disciplineData?.data ?? []

  const groupedRows = useMemo(() => {
    const map = new Map<
      string,
      {
        department_name: string
        project_name: string
        assignee_name: string
        tasks_count: number
      }
    >()

    for (const row of rows) {
      const key = `${row.department_name}|${row.project_name}|${row.assignee_name}`
      const existing = map.get(key)
      if (existing) {
        existing.tasks_count += 1
      } else {
        map.set(key, {
          department_name: row.department_name,
          project_name: row.project_name,
          assignee_name: row.assignee_name,
          tasks_count: 1,
        })
      }
    }

    return [...map.values()].sort((a, b) => b.tasks_count - a.tasks_count)
  }, [rows])

  const topDepartments = useMemo(() => {
    const map = new Map<string, number>()
    for (const row of rows) {
      map.set(row.department_name, (map.get(row.department_name) ?? 0) + 1)
    }
    return [...map.entries()]
      .map(([department_name, count]) => ({ department_name, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10)
  }, [rows])

  const overdueCount = rows.length
  const closedOverdueCount = rows.filter((row) => Boolean(row.closed_at)).length

  const download = async (kind: "xlsx" | "docx") => {
    try {
      setDownloading(kind)
      const token = localStorage.getItem("access_token") || ""
      const url =
        kind === "xlsx"
          ? trackerApi.reportDisciplineXlsxUrl()
          : trackerApi.reportDisciplineDocxUrl()
      const response = await fetch(url, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      if (!response.ok) {
        throw new Error(`Ошибка выгрузки (${response.status})`)
      }
      const blob = await response.blob()
      const objectUrl = URL.createObjectURL(blob)
      const anchor = document.createElement("a")
      anchor.href = objectUrl
      anchor.download =
        kind === "xlsx"
          ? "discipline-report.xlsx"
          : "discipline-report.docx"
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(objectUrl)
      showToast.success("Успешно", `Файл ${kind.toUpperCase()} выгружен`)
    } catch (error) {
      showToast.error("Не удалось выгрузить файл", error)
    } finally {
      setDownloading(null)
    }
  }

  return (
    <Container maxW="full" py={6}>
      <HStack justify="space-between" mb={4} align="start">
        <Box>
          <Heading size="lg" mb={1}>
            Справка по исполнительской дисциплине
          </Heading>
          <Text color="gray.600">
            Просроченные задачи по департаментам, проектам и исполнителям
          </Text>
        </Box>
        <HStack>
          <Button
            onClick={() => download("xlsx")}
            isLoading={downloading === "xlsx"}
          >
            XLSX
          </Button>
          <Button
            onClick={() => download("docx")}
            isLoading={downloading === "docx"}
          >
            DOCX
          </Button>
        </HStack>
      </HStack>

      <Grid
        templateColumns={{ base: "1fr", md: "repeat(4, 1fr)" }}
        gap={4}
        mb={4}
      >
        <Stat
          borderWidth="1px"
          borderColor="ui.border"
          borderRadius="md"
          p={3}
          bg="white"
        >
          <StatLabel>Всего задач</StatLabel>
          <StatNumber>{summary?.total_tasks ?? 0}</StatNumber>
        </Stat>
        <Stat
          borderWidth="1px"
          borderColor="ui.border"
          borderRadius="md"
          p={3}
          bg="white"
        >
          <StatLabel>Просроченных</StatLabel>
          <StatNumber>{overdueCount}</StatNumber>
        </Stat>
        <Stat
          borderWidth="1px"
          borderColor="ui.border"
          borderRadius="md"
          p={3}
          bg="white"
        >
          <StatLabel>Закрыто с просрочкой</StatLabel>
          <StatNumber>{closedOverdueCount}</StatNumber>
        </Stat>
        <Stat
          borderWidth="1px"
          borderColor="ui.border"
          borderRadius="md"
          p={3}
          bg="white"
        >
          <StatLabel>Групп по дисциплине</StatLabel>
          <StatNumber>{groupedRows.length}</StatNumber>
        </Stat>
      </Grid>

      <Grid templateColumns={{ base: "1fr", xl: "2fr 1fr" }} gap={4}>
        <GridItem>
          <Box
            borderWidth="1px"
            borderColor="ui.border"
            borderRadius="md"
            overflow="hidden"
            bg="white"
          >
            <Box px={4} py={3} borderBottomWidth="1px" borderColor="ui.border">
              <Text fontWeight="700">
                По департаментам / проектам / исполнителям
              </Text>
            </Box>
            <Box overflowX="auto">
              <Table size="sm">
                <Thead>
                  <Tr>
                    <Th>Департамент</Th>
                    <Th>Проект</Th>
                    <Th>Исполнитель</Th>
                    <Th isNumeric>Просроченных задач</Th>
                  </Tr>
                </Thead>
                <Tbody>
                  {groupedRows.map((row) => (
                    <Tr
                      key={`${row.department_name}-${row.project_name}-${row.assignee_name}`}
                    >
                      <Td>{row.department_name}</Td>
                      <Td>{row.project_name}</Td>
                      <Td>{row.assignee_name}</Td>
                      <Td isNumeric>{row.tasks_count}</Td>
                    </Tr>
                  ))}
                </Tbody>
              </Table>
              {!groupedRows.length && !isLoading && (
                <Text px={4} py={4} color="gray.600">
                  Просроченных задач не найдено.
                </Text>
              )}
            </Box>
          </Box>
        </GridItem>

        <GridItem>
          <Box
            borderWidth="1px"
            borderColor="ui.border"
            borderRadius="md"
            overflow="hidden"
            bg="white"
          >
            <Box px={4} py={3} borderBottomWidth="1px" borderColor="ui.border">
              <Text fontWeight="700">Топ департаментов</Text>
            </Box>
            <Table size="sm">
              <Thead>
                <Tr>
                  <Th>Департамент</Th>
                  <Th isNumeric>Просроченных</Th>
                </Tr>
              </Thead>
              <Tbody>
                {topDepartments.map((item) => (
                  <Tr key={item.department_name}>
                    <Td>{item.department_name}</Td>
                    <Td isNumeric>{item.count}</Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </Box>
        </GridItem>
      </Grid>
    </Container>
  )
}
