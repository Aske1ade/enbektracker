import {
  Badge,
  Box,
  Button,
  Collapse,
  Container,
  Flex,
  FormControl,
  FormLabel,
  Grid,
  HStack,
  Heading,
  Icon,
  Input,
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalFooter,
  ModalHeader,
  ModalOverlay,
  Select,
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
  Text,
  VStack,
  useDisclosure,
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link, Outlet, createFileRoute, useMatchRoute } from "@tanstack/react-router"
import { useMemo, useState } from "react"
import { FiFolder, FiLayers, FiSearch, FiUsers } from "react-icons/fi"

import type { UserPublic } from "../../client"
import useCustomToast from "../../hooks/useCustomToast"
import { trackerApi } from "../../services/trackerApi"
import type { Project } from "../../types/tracker"
import {
  fallbackAccentBySeed,
  readProjectAccent,
  resolveProjectIconPath,
} from "../../utils/projectVisuals"

export const Route = createFileRoute("/_layout/projects")({
  component: ProjectsPage,
})

type ProjectGroup = {
  blockName: string
  projects: Project[]
}

function ProjectsPage() {
  const matchRoute = useMatchRoute()
  const isProjectDetailsPath = Boolean(
    matchRoute({
      to: "/projects/$projectId",
      fuzzy: false,
    }),
  )

  const queryClient = useQueryClient()
  const currentUser = queryClient.getQueryData<UserPublic & { system_role?: string }>([
    "currentUser",
  ])
  const canCreateProject =
    Boolean(currentUser?.is_superuser) ||
    currentUser?.system_role === "system_admin" ||
    currentUser?.system_role === "admin"
  const modal = useDisclosure()
  const showToast = useCustomToast()

  const [search, setSearch] = useState("")
  const [blockFilter, setBlockFilter] = useState("all")
  const [showFilters, setShowFilters] = useState(false)
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")

  const { data, isLoading } = useQuery({
    queryKey: ["projects", "wall-list"],
    queryFn: () =>
      trackerApi.listProjects({
        page: 1,
        page_size: 500,
        sort_by: "name",
        sort_order: "asc",
      }),
  })

  const createMutation = useMutation({
    mutationFn: () =>
      trackerApi.createProject({
        name,
        icon: null,
        description,
      }),
    onSuccess: () => {
      setName("")
      setDescription("")
      modal.onClose()
      queryClient.invalidateQueries({ queryKey: ["projects"] })
      showToast.success("Успешно", "Проект создан")
    },
    onError: (error) => showToast.error("Не удалось создать проект", error),
  })

  const groupedProjects = useMemo<ProjectGroup[]>(() => {
    const rows = data?.data ?? []
    const query = search.trim().toLowerCase()

    const filtered = rows.filter((project) => {
      if (!query) return true
      const haystack = [
        project.name,
        project.description || "",
        project.organization_name || "",
        project.block_name || "",
      ]
        .join(" ")
        .toLowerCase()
      return haystack.includes(query)
    })

    const grouped = new Map<string, Project[]>()
    for (const project of filtered) {
      const blockName = project.block_name?.trim() || "Без группы"
      if (blockFilter !== "all" && blockFilter !== blockName) {
        continue
      }
      const bucket = grouped.get(blockName) ?? []
      bucket.push(project)
      grouped.set(blockName, bucket)
    }

    return [...grouped.entries()]
      .map(([blockName, projects]) => ({
        blockName,
        projects: projects.sort((a, b) => a.name.localeCompare(b.name, "ru")),
      }))
      .sort((a, b) => {
        if (a.blockName === "Без группы") return 1
        if (b.blockName === "Без группы") return -1
        return a.blockName.localeCompare(b.blockName, "ru")
      })
  }, [blockFilter, data?.data, search])

  const blockOptions = useMemo(() => {
    const set = new Set<string>()
    for (const project of data?.data ?? []) {
      set.add(project.block_name?.trim() || "Без группы")
    }
    return [...set].sort((a, b) => {
      if (a === "Без группы") return 1
      if (b === "Без группы") return -1
      return a.localeCompare(b, "ru")
    })
  }, [data?.data])

  const visibleProjectsCount = groupedProjects.reduce(
    (acc, group) => acc + group.projects.length,
    0,
  )
  const allProjectsCount = data?.data?.length ?? 0
  const groupsTotalCount = useMemo(() => {
    const names = new Set<string>()
    for (const project of data?.data ?? []) {
      for (const departmentName of project.department_names ?? []) {
        if (departmentName?.trim()) names.add(departmentName.trim())
      }
      if (project.department_name?.trim()) names.add(project.department_name.trim())
    }
    return names.size
  }, [data?.data])
  const participantsTotal = useMemo(() => {
    const rows = data?.data ?? []
    const uniqueParticipantIds = new Set<number>()
    let hasMemberIds = false

    for (const project of rows) {
      const memberIds = project.member_user_ids ?? []
      if (memberIds.length > 0) {
        hasMemberIds = true
      }
      for (const memberId of memberIds) {
        uniqueParticipantIds.add(memberId)
      }
    }

    if (hasMemberIds) {
      return uniqueParticipantIds.size
    }
    return rows.reduce((acc, project) => acc + (project.members_count ?? 0), 0)
  }, [data?.data])
  const projectAccentById = useMemo(() => {
    const map = new Map<number, string>()
    for (const project of data?.data ?? []) {
      const stored = readProjectAccent(project.id)
      map.set(
        project.id,
        stored ||
          fallbackAccentBySeed(
            project.department_name ||
              project.block_name ||
              project.organization_name ||
              project.name,
          ),
      )
    }
    return map
  }, [data?.data])

  if (isProjectDetailsPath) {
    return <Outlet />
  }

  return (
    <Container maxW="full" py={6}>
      <Box
        borderRadius="16px"
        bgGradient="linear(120deg, #1D3E66 0%, #29537F 45%, #3D6D9D 100%)"
        color="white"
        px={{ base: 4, md: 6 }}
        py={{ base: 4, md: 5 }}
        mb={4}
        boxShadow="0 16px 30px rgba(19, 39, 63, 0.22)"
      >
        <Flex justify="space-between" align={{ base: "start", md: "center" }} gap={4} wrap="wrap">
          <Box maxW="760px">
            <Text fontSize="xs" letterSpacing="0.12em" textTransform="uppercase" color="whiteAlpha.800">
              Project Wall
            </Text>
            <Heading mt={1} size="lg" color="white">
              Проекты
            </Heading>
            <Text mt={2} color="whiteAlpha.900">
              Проекты сгруппированы по блокам и организациям, доступ в проект и стену в один клик.
            </Text>
          </Box>
          <HStack spacing={2}>
            <Button
              size="sm"
              variant="subtle"
              bg="whiteAlpha.300"
              color="white"
              _hover={{ bg: "whiteAlpha.400" }}
              onClick={() => setShowFilters((prev) => !prev)}
            >
              {showFilters ? "Скрыть фильтры" : "Показать фильтры"}
            </Button>
            {canCreateProject ? (
              <Button variant="primary" onClick={modal.onOpen}>
                Создать проект
              </Button>
            ) : null}
          </HStack>
        </Flex>
      </Box>

      <SimpleGrid columns={{ base: 1, sm: 2, lg: 4 }} spacing={3} mb={5}>
        <Box borderWidth="1px" borderColor="ui.border" bg="white" borderRadius="12px" p={3} boxShadow="sm">
          <Stat>
            <HStack spacing={2} mb={1}>
              <Icon as={FiFolder} color="ui.main" />
              <StatLabel m={0}>Проекты</StatLabel>
            </HStack>
            <StatNumber>{allProjectsCount}</StatNumber>
          </Stat>
        </Box>
        <Box borderWidth="1px" borderColor="ui.border" bg="white" borderRadius="12px" p={3} boxShadow="sm">
          <Stat>
            <HStack spacing={2} mb={1}>
              <Icon as={FiLayers} color="ui.main" />
              <StatLabel m={0}>Группы</StatLabel>
            </HStack>
            <StatNumber>{groupsTotalCount}</StatNumber>
          </Stat>
        </Box>
        <Box borderWidth="1px" borderColor="ui.border" bg="white" borderRadius="12px" p={3} boxShadow="sm">
          <Stat>
            <HStack spacing={2} mb={1}>
              <Icon as={FiUsers} color="ui.main" />
              <StatLabel m={0}>Участники</StatLabel>
            </HStack>
            <StatNumber>{participantsTotal}</StatNumber>
          </Stat>
        </Box>
        <Box borderWidth="1px" borderColor="ui.border" bg="white" borderRadius="12px" p={3} boxShadow="sm">
          <Stat>
            <HStack spacing={2} mb={1}>
              <Icon as={FiSearch} color="ui.main" />
              <StatLabel m={0}>В выборке</StatLabel>
            </HStack>
            <StatNumber>{visibleProjectsCount}</StatNumber>
          </Stat>
        </Box>
      </SimpleGrid>

      <Collapse in={showFilters} animateOpacity>
        <Box
          borderWidth="1px"
          borderColor="ui.border"
          borderRadius="12px"
          p={4}
          bg="white"
          boxShadow="sm"
          mb={4}
        >
          <Grid templateColumns={{ base: "1fr", md: "1.4fr 1fr" }} gap={3}>
            <FormControl>
              <FormLabel>Поиск проекта</FormLabel>
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Название, описание, организация"
              />
            </FormControl>
            <FormControl>
              <FormLabel>Группа (блок)</FormLabel>
              <Select value={blockFilter} onChange={(e) => setBlockFilter(e.target.value)}>
                <option value="all">Все группы</option>
                {blockOptions.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <HStack mt={3} spacing={2} flexWrap="wrap">
            <Badge
              cursor="pointer"
              borderRadius="full"
              px={3}
              py={1}
              colorScheme={blockFilter === "all" ? "blue" : "gray"}
              onClick={() => setBlockFilter("all")}
            >
              Все
            </Badge>
            {blockOptions.map((option) => (
              <Badge
                key={`block-chip-${option}`}
                cursor="pointer"
                borderRadius="full"
                px={3}
                py={1}
                colorScheme={blockFilter === option ? "blue" : "gray"}
                onClick={() => setBlockFilter(option)}
              >
                {option}
              </Badge>
            ))}
          </HStack>
        </Box>
      </Collapse>

      <VStack align="stretch" spacing={4}>
        {isLoading && (
          <Box borderWidth="1px" borderColor="ui.border" borderRadius="12px" p={6} bg="white">
            <Text>Загрузка проектов...</Text>
          </Box>
        )}

        {!isLoading && groupedProjects.length === 0 && (
          <Box borderWidth="1px" borderColor="ui.border" borderRadius="12px" p={6} bg="white">
            <Text>Проекты не найдены</Text>
          </Box>
        )}

        {!isLoading &&
          groupedProjects.map((group) => {
            const groupAccent =
              projectAccentById.get(group.projects[0]?.id ?? -1) ||
              fallbackAccentBySeed(group.blockName)
            return (
            <Box
              key={group.blockName}
              borderWidth="1px"
              borderColor="ui.border"
              borderRadius="12px"
              bg="white"
              overflow="hidden"
              boxShadow="sm"
              borderTopWidth="4px"
              borderTopColor={groupAccent}
            >
              <HStack
                justify="space-between"
                px={4}
                py={3}
                borderBottomWidth="1px"
                borderColor="ui.border"
                bg={hexToRgba(groupAccent, 0.1)}
              >
                <Heading size="sm">{group.blockName}</Heading>
                <Badge borderRadius="full" px={2} py={0.5} bg={hexToRgba(groupAccent, 0.18)} color="ui.main" fontSize="11px">
                  {group.projects.length}
                </Badge>
              </HStack>

              <Grid templateColumns={{ base: "1fr", xl: "repeat(2, minmax(0, 1fr))" }} gap={0}>
                {group.projects.map((project) => (
                  <Box
                    key={project.id}
                    as={Link}
                    to="/projects/$projectId"
                    params={{ projectId: String(project.id) }}
                    px={4}
                    py={3}
                    borderTopWidth="1px"
                    borderRightWidth={{ xl: "1px" }}
                    borderColor="ui.border"
                    _hover={{ bg: "#F8FAFD" }}
                  >
                    <HStack justify="space-between" align="start" gap={3}>
                      <Box minW={0}>
                        <HStack spacing={2} align="center">
                          <Box
                            w="34px"
                            h="34px"
                            borderRadius="8px"
                            borderWidth="1px"
                            borderColor="ui.border"
                            bg="ui.secondary"
                            display="flex"
                            alignItems="center"
                            justifyContent="center"
                            overflow="hidden"
                          >
                            <Box
                              as="img"
                              src={resolveProjectIconPath(project.icon)}
                              alt={project.name}
                              w="22px"
                              h="22px"
                              objectFit="contain"
                            />
                          </Box>
                          <Text fontWeight="700" noOfLines={1}>
                            {project.name}
                          </Text>
                        </HStack>
                        <Text fontSize="sm" color="ui.muted" noOfLines={2} mt={0.5}>
                          {project.description || "Описание не указано"}
                        </Text>
                        <HStack mt={2} spacing={2} flexWrap="wrap">
                          <Badge borderRadius="full" fontSize="11px" px={2} py={0.5}>
                            Участн.: {project.members_count ?? 0}
                          </Badge>
                          <Badge borderRadius="full" fontSize="11px" px={2} py={0.5}>
                            Задач: {project.tasks_count ?? 0}
                          </Badge>
                          <Badge borderRadius="full" fontSize="11px" px={2} py={0.5}>
                            {project.organization_name || "Без организации"}
                          </Badge>
                          <Badge borderRadius="full" colorScheme="purple" fontSize="11px" px={2} py={0.5}>
                            {project.department_name ||
                              project.department_names?.join(", ") ||
                              "Без департамента"}
                          </Badge>
                        </HStack>
                      </Box>
                      <Text color="ui.main" fontWeight="600" whiteSpace="nowrap">
                        Открыть →
                      </Text>
                    </HStack>
                  </Box>
                ))}
              </Grid>
            </Box>
            )
          })}
      </VStack>

      <Modal isOpen={modal.isOpen && canCreateProject} onClose={modal.onClose} isCentered>
        <ModalOverlay />
        <ModalContent borderRadius="12px">
          <ModalHeader>Новый проект</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <FormControl isRequired>
              <FormLabel>Название</FormLabel>
              <Input value={name} onChange={(e) => setName(e.target.value)} />
            </FormControl>
            <Box mt={3} p={3} borderWidth="1px" borderColor="ui.border" borderRadius="md">
              <Text fontSize="sm" color="ui.muted">
                Иконку проекта можно загрузить после создания в «Настройки проекта».
              </Text>
            </Box>
            <FormControl mt={3}>
              <FormLabel>Описание</FormLabel>
              <Input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </FormControl>
          </ModalBody>
          <ModalFooter gap={3}>
            <Button
              onClick={() => createMutation.mutate()}
              isLoading={createMutation.isPending}
              isDisabled={!name.trim()}
            >
              Создать
            </Button>
            <Button variant="subtle" onClick={modal.onClose}>
              Отмена
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Container>
  )
}

function hexToRgba(color: string, alpha: number): string {
  const hex = color.replace("#", "")
  const normalized = hex.length === 3 ? hex.split("").map((ch) => ch + ch).join("") : hex
  const r = Number.parseInt(normalized.slice(0, 2), 16)
  const g = Number.parseInt(normalized.slice(2, 4), 16)
  const b = Number.parseInt(normalized.slice(4, 6), 16)
  if ([r, g, b].some((part) => Number.isNaN(part))) return color
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}
