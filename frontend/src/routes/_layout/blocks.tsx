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
  GridItem,
  Heading,
  HStack,
  Icon,
  IconButton,
  Input,
  Select,
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
  Tab,
  TabList,
  TabPanel,
  TabPanels,
  Tabs,
  Text,
  Textarea,
  VStack,
  useColorModeValue,
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useEffect, useMemo, useState } from "react"
import {
  FiBriefcase,
  FiChevronUp,
  FiFolder,
  FiLayers,
  FiPlus,
  FiSettings,
  FiUsers,
} from "react-icons/fi"

import useCustomToast from "../../hooks/useCustomToast"
import { trackerApi } from "../../services/trackerApi"

export const Route = createFileRoute("/_layout/blocks")({
  component: GroupManagementPage,
})

type RoleName = "owner" | "manager" | "member"

const ROLE_OPTIONS: Array<{ value: RoleName; label: string }> = [
  { value: "owner", label: "Директор" },
  { value: "manager", label: "Руководитель" },
  { value: "member", label: "Участник" },
]

function roleLabel(roleName: string): string {
  const found = ROLE_OPTIONS.find((item) => item.value === roleName)
  return found?.label || roleName
}

type TreeNodeLike = {
  id: number
  name: string
  children?: TreeNodeLike[]
}

function filterTreeByName(nodes: TreeNodeLike[], query: string): TreeNodeLike[] {
  const normalized = query.trim().toLowerCase()
  if (!normalized) return nodes

  const walk = (source: TreeNodeLike[]): TreeNodeLike[] => {
    const result: TreeNodeLike[] = []
    for (const node of source) {
      const children = walk(node.children || [])
      const selfMatch = node.name.toLowerCase().includes(normalized)
      if (!selfMatch && !children.length) {
        continue
      }
      result.push({
        ...node,
        children,
      })
    }
    return result
  }

  return walk(nodes)
}

function GroupManagementPage() {
  const showToast = useCustomToast()
  const queryClient = useQueryClient()
  const cardBg = useColorModeValue("white", "#162235")
  const panelGradient = useColorModeValue(
    "linear(180deg, #FFFFFF 0%, #F8FBFF 100%)",
    "linear(180deg, #1A2A42 0%, #142033 100%)",
  )
  const panelGradientAlt = useColorModeValue(
    "linear(180deg, #FFFFFF 0%, #F9FBFF 100%)",
    "linear(180deg, #18283f 0%, #132033 100%)",
  )
  const selectedNodeBg = useColorModeValue("#E9F0FA", "rgba(59, 130, 246, 0.20)")
  const nodeHoverBg = useColorModeValue("#F4F8FE", "rgba(255, 255, 255, 0.08)")
  const activeMemberBg = useColorModeValue("rgba(46, 125, 50, 0.04)", "rgba(46, 125, 50, 0.16)")
  const inactiveMemberBg = useColorModeValue("white", "#132033")

  const [selectedOrganizationId, setSelectedOrganizationId] = useState<number | null>(null)
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null)

  const [organizationForm, setOrganizationForm] = useState({
    name: "",
    code: "",
    description: "",
    parent_organization_id: "",
  })
  const [organizationEditForm, setOrganizationEditForm] = useState({
    name: "",
    code: "",
    description: "",
    parent_organization_id: "",
  })

  const [groupForm, setGroupForm] = useState({
    name: "",
    code: "",
    description: "",
    parent_group_id: "",
  })
  const [groupEditForm, setGroupEditForm] = useState({
    name: "",
    code: "",
    description: "",
    parent_group_id: "",
  })

  const [organizationMemberForm, setOrganizationMemberForm] = useState({
    user_id: "",
    role_name: "member" as RoleName,
  })
  const [groupMemberForm, setGroupMemberForm] = useState({
    user_id: "",
    role_name: "member" as RoleName,
  })

  const [organizationMemberRoles, setOrganizationMemberRoles] = useState<Record<number, RoleName>>(
    {},
  )
  const [groupMemberRoles, setGroupMemberRoles] = useState<Record<number, RoleName>>({})
  const [organizationSearch, setOrganizationSearch] = useState("")
  const [groupSearch, setGroupSearch] = useState("")
  const [organizationMemberSearch, setOrganizationMemberSearch] = useState("")
  const [groupMemberSearch, setGroupMemberSearch] = useState("")
  const [organizationUserSearch, setOrganizationUserSearch] = useState("")
  const [groupUserSearch, setGroupUserSearch] = useState("")
  const [organizationMemberRoleFilter, setOrganizationMemberRoleFilter] = useState<"all" | RoleName>(
    "all",
  )
  const [groupMemberRoleFilter, setGroupMemberRoleFilter] = useState<"all" | RoleName>("all")
  const [showCreateOrganization, setShowCreateOrganization] = useState(false)
  const [showOrganizationSettings, setShowOrganizationSettings] = useState(false)
  const [showCreateGroup, setShowCreateGroup] = useState(false)
  const [showGroupSettings, setShowGroupSettings] = useState(false)
  const [showOrganizationMembersSection, setShowOrganizationMembersSection] = useState(false)

  const { data: usersData } = useQuery({
    queryKey: ["all-users-for-groups"],
    queryFn: () => trackerApi.listUsers(),
  })

  const { data: organizationsData, isLoading: organizationsLoading } = useQuery({
    queryKey: ["organizations"],
    queryFn: () => trackerApi.listOrganizations(),
  })

  const { data: organizationsTreeData } = useQuery({
    queryKey: ["organizations-tree"],
    queryFn: () => trackerApi.listOrganizationTree(),
  })

  useEffect(() => {
    const organizations = organizationsData?.data ?? []
    if (!organizations.length) {
      setSelectedOrganizationId(null)
      return
    }
    setSelectedOrganizationId((prev) => {
      if (prev && organizations.some((item) => item.id === prev)) {
        return prev
      }
      return organizations[0].id
    })
  }, [organizationsData?.data])

  const { data: groupsData, isLoading: groupsLoading } = useQuery({
    queryKey: ["organization-groups", selectedOrganizationId],
    queryFn: () => trackerApi.getOrganizationGroups(selectedOrganizationId as number),
    enabled: selectedOrganizationId !== null,
  })

  const { data: groupsTreeData } = useQuery({
    queryKey: ["organization-groups-tree", selectedOrganizationId],
    queryFn: () => trackerApi.getOrganizationGroupsTree(selectedOrganizationId as number),
    enabled: selectedOrganizationId !== null,
  })

  useEffect(() => {
    const groups = groupsData?.data ?? []
    if (!groups.length) {
      setSelectedGroupId(null)
      return
    }
    setSelectedGroupId((prev) => {
      if (prev && groups.some((item) => item.id === prev)) {
        return prev
      }
      return null
    })
  }, [groupsData?.data])

  const { data: organizationMembersData, isLoading: organizationMembersLoading } = useQuery({
    queryKey: ["organization-members", selectedOrganizationId],
    queryFn: () => trackerApi.listOrganizationMembers(selectedOrganizationId as number),
    enabled: selectedOrganizationId !== null,
  })

  const { data: groupMembersData, isLoading: groupMembersLoading } = useQuery({
    queryKey: ["group-members", selectedGroupId],
    queryFn: () => trackerApi.listOrganizationGroupMembers(selectedGroupId as number),
    enabled: selectedGroupId !== null,
  })

  const selectedOrganization = useMemo(
    () =>
      (organizationsData?.data ?? []).find(
        (organization) => organization.id === selectedOrganizationId,
      ),
    [organizationsData?.data, selectedOrganizationId],
  )

  const selectedGroup = useMemo(
    () => (groupsData?.data ?? []).find((group) => group.id === selectedGroupId),
    [groupsData?.data, selectedGroupId],
  )

  useEffect(() => {
    if (!selectedOrganization) {
      setOrganizationEditForm({
        name: "",
        code: "",
        description: "",
        parent_organization_id: "",
      })
      return
    }
    setOrganizationEditForm({
      name: selectedOrganization.name,
      code: selectedOrganization.code || "",
      description: selectedOrganization.description || "",
      parent_organization_id: selectedOrganization.parent_organization_id
        ? String(selectedOrganization.parent_organization_id)
        : "",
    })
  }, [selectedOrganization])

  useEffect(() => {
    if (!selectedGroup) {
      setGroupEditForm({
        name: "",
        code: "",
        description: "",
        parent_group_id: "",
      })
      return
    }
    setGroupEditForm({
      name: selectedGroup.name,
      code: selectedGroup.code || "",
      description: selectedGroup.description || "",
      parent_group_id: selectedGroup.parent_group_id ? String(selectedGroup.parent_group_id) : "",
    })
  }, [selectedGroup])

  useEffect(() => {
    const next: Record<number, RoleName> = {}
    for (const member of organizationMembersData?.data ?? []) {
      const role = (member.role_name || "member") as RoleName
      next[member.user_id] = ROLE_OPTIONS.some((item) => item.value === role) ? role : "member"
    }
    setOrganizationMemberRoles(next)
  }, [organizationMembersData?.data])

  useEffect(() => {
    const next: Record<number, RoleName> = {}
    for (const member of groupMembersData?.data ?? []) {
      const role = (member.role_name || "member") as RoleName
      next[member.user_id] = ROLE_OPTIONS.some((item) => item.value === role) ? role : "member"
    }
    setGroupMemberRoles(next)
  }, [groupMembersData?.data])

  const refreshOrganizations = () => {
    queryClient.invalidateQueries({ queryKey: ["organizations"] })
    queryClient.invalidateQueries({ queryKey: ["organizations-tree"] })
  }

  const refreshSelectedOrganization = () => {
    queryClient.invalidateQueries({ queryKey: ["organization-groups", selectedOrganizationId] })
    queryClient.invalidateQueries({ queryKey: ["organization-groups-tree", selectedOrganizationId] })
    queryClient.invalidateQueries({ queryKey: ["organization-members", selectedOrganizationId] })
    queryClient.invalidateQueries({ queryKey: ["organizations"] })
    queryClient.invalidateQueries({ queryKey: ["organizations-tree"] })
  }

  const refreshSelectedGroup = () => {
    queryClient.invalidateQueries({ queryKey: ["group-members", selectedGroupId] })
    queryClient.invalidateQueries({ queryKey: ["organization-groups", selectedOrganizationId] })
    queryClient.invalidateQueries({ queryKey: ["organization-groups-tree", selectedOrganizationId] })
  }

  const createOrganizationMutation = useMutation({
    mutationFn: () =>
      trackerApi.createOrganization({
        name: organizationForm.name,
        code: organizationForm.code || null,
        description: organizationForm.description || null,
        parent_organization_id: organizationForm.parent_organization_id
          ? Number(organizationForm.parent_organization_id)
          : null,
      }),
    onSuccess: (created) => {
      setOrganizationForm({
        name: "",
        code: "",
        description: "",
        parent_organization_id: "",
      })
      refreshOrganizations()
      setSelectedOrganizationId(created.id)
      showToast.success("Успешно", "Организация создана")
    },
    onError: (error) => showToast.error("Не удалось создать организацию", error),
  })

  const updateOrganizationMutation = useMutation({
    mutationFn: () =>
      trackerApi.updateOrganization(selectedOrganizationId as number, {
        name: organizationEditForm.name,
        code: organizationEditForm.code || null,
        description: organizationEditForm.description || null,
        parent_organization_id: organizationEditForm.parent_organization_id
          ? Number(organizationEditForm.parent_organization_id)
          : null,
      }),
    onSuccess: () => {
      refreshOrganizations()
      refreshSelectedOrganization()
      showToast.success("Успешно", "Организация обновлена")
    },
    onError: (error) => showToast.error("Не удалось обновить организацию", error),
  })

  const deleteOrganizationMutation = useMutation({
    mutationFn: () => trackerApi.deleteOrganization(selectedOrganizationId as number),
    onSuccess: () => {
      refreshOrganizations()
      setSelectedGroupId(null)
      showToast.success("Успешно", "Организация удалена")
    },
    onError: (error) => showToast.error("Не удалось удалить организацию", error),
  })

  const createGroupMutation = useMutation({
    mutationFn: () =>
      trackerApi.createOrganizationGroup(selectedOrganizationId as number, {
        name: groupForm.name,
        code: groupForm.code || null,
        description: groupForm.description || null,
        parent_group_id: groupForm.parent_group_id ? Number(groupForm.parent_group_id) : null,
      }),
    onSuccess: (created) => {
      setGroupForm({
        name: "",
        code: "",
        description: "",
        parent_group_id: "",
      })
      refreshSelectedOrganization()
      setSelectedGroupId(created.id)
      showToast.success("Успешно", "Группа создана")
    },
    onError: (error) => showToast.error("Не удалось создать группу", error),
  })

  const updateGroupMutation = useMutation({
    mutationFn: () =>
      trackerApi.updateOrganizationGroup(selectedOrganizationId as number, selectedGroupId as number, {
        name: groupEditForm.name,
        code: groupEditForm.code || null,
        description: groupEditForm.description || null,
        parent_group_id: groupEditForm.parent_group_id ? Number(groupEditForm.parent_group_id) : null,
      }),
    onSuccess: () => {
      refreshSelectedGroup()
      showToast.success("Успешно", "Группа обновлена")
    },
    onError: (error) => showToast.error("Не удалось обновить группу", error),
  })

  const deleteGroupMutation = useMutation({
    mutationFn: () =>
      trackerApi.deleteOrganizationGroup(selectedOrganizationId as number, selectedGroupId as number),
    onSuccess: () => {
      refreshSelectedOrganization()
      setSelectedGroupId(null)
      showToast.success("Успешно", "Группа удалена")
    },
    onError: (error) => showToast.error("Не удалось удалить группу", error),
  })

  const addOrganizationMemberMutation = useMutation({
    mutationFn: () =>
      trackerApi.addOrganizationMember(selectedOrganizationId as number, {
        user_id: Number(organizationMemberForm.user_id),
        role_name: organizationMemberForm.role_name,
      }),
    onSuccess: () => {
      setOrganizationMemberForm({ user_id: "", role_name: "member" })
      refreshSelectedOrganization()
      showToast.success("Успешно", "Участник добавлен в организацию")
    },
    onError: (error) => showToast.error("Не удалось добавить участника", error),
  })

  const updateOrganizationMemberMutation = useMutation({
    mutationFn: ({ userId, roleName }: { userId: number; roleName: RoleName }) =>
      trackerApi.updateOrganizationMember(selectedOrganizationId as number, userId, {
        role_name: roleName,
      }),
    onSuccess: () => {
      refreshSelectedOrganization()
      showToast.success("Успешно", "Роль участника организации обновлена")
    },
    onError: (error) => showToast.error("Не удалось обновить роль в организации", error),
  })

  const removeOrganizationMemberMutation = useMutation({
    mutationFn: (userId: number) =>
      trackerApi.removeOrganizationMember(selectedOrganizationId as number, userId),
    onSuccess: () => {
      refreshSelectedOrganization()
      showToast.success("Успешно", "Участник удалён из организации")
    },
    onError: (error) => showToast.error("Не удалось удалить участника", error),
  })

  const addGroupMemberMutation = useMutation({
    mutationFn: () =>
      trackerApi.addOrganizationGroupMember(selectedGroupId as number, {
        user_id: Number(groupMemberForm.user_id),
        role_name: groupMemberForm.role_name,
      }),
    onSuccess: () => {
      setGroupMemberForm({ user_id: "", role_name: "member" })
      refreshSelectedGroup()
      refreshSelectedOrganization()
      showToast.success("Успешно", "Участник добавлен в группу")
    },
    onError: (error) => showToast.error("Не удалось добавить участника в группу", error),
  })

  const updateGroupMemberMutation = useMutation({
    mutationFn: ({ userId, roleName }: { userId: number; roleName: RoleName }) =>
      trackerApi.updateOrganizationGroupMember(selectedGroupId as number, userId, {
        role_name: roleName,
      }),
    onSuccess: () => {
      refreshSelectedGroup()
      refreshSelectedOrganization()
      showToast.success("Успешно", "Роль участника группы обновлена")
    },
    onError: (error) => showToast.error("Не удалось обновить роль в группе", error),
  })

  const removeGroupMemberMutation = useMutation({
    mutationFn: (userId: number) =>
      trackerApi.removeOrganizationGroupMember(selectedGroupId as number, userId),
    onSuccess: () => {
      refreshSelectedGroup()
      showToast.success("Успешно", "Участник удалён из группы")
    },
    onError: (error) => showToast.error("Не удалось удалить участника", error),
  })

  const organizationParentOptions = useMemo(() => {
    const options: Array<{ id: number; label: string }> = []
    const walk = (nodes: Array<{ id: number; name: string; children: any[] }>, level: number) => {
      for (const node of nodes) {
        options.push({ id: node.id, label: `${"· ".repeat(level)}${node.name}` })
        walk(node.children || [], level + 1)
      }
    }
    walk((organizationsTreeData?.data as any[]) ?? [], 0)
    return options
  }, [organizationsTreeData?.data])

  const groupParentOptions = useMemo(() => {
    const options: Array<{ id: number; label: string }> = []
    const walk = (nodes: Array<{ id: number; name: string; children: any[] }>, level: number) => {
      for (const node of nodes) {
        options.push({ id: node.id, label: `${"· ".repeat(level)}${node.name}` })
        walk(node.children || [], level + 1)
      }
    }
    walk((groupsTreeData?.data as any[]) ?? [], 0)
    return options
  }, [groupsTreeData?.data])

  const usersOptions = useMemo(
    () =>
      (usersData?.data ?? [])
        .slice()
        .sort((a, b) => (a.full_name || a.email).localeCompare(b.full_name || b.email, "ru")),
    [usersData?.data],
  )

  const filteredOrganizationUsersOptions = useMemo(() => {
    const query = organizationUserSearch.trim().toLowerCase()
    if (!query) return usersOptions
    return usersOptions.filter((user) =>
      `${user.full_name || ""} ${user.email || ""}`.toLowerCase().includes(query),
    )
  }, [organizationUserSearch, usersOptions])

  const filteredGroupUsersOptions = useMemo(() => {
    const query = groupUserSearch.trim().toLowerCase()
    if (!query) return usersOptions
    return usersOptions.filter((user) =>
      `${user.full_name || ""} ${user.email || ""}`.toLowerCase().includes(query),
    )
  }, [groupUserSearch, usersOptions])

  const filteredOrganizationTree = useMemo(
    () =>
      filterTreeByName(
        ((organizationsTreeData?.data as TreeNodeLike[]) ?? []).map((node) => ({
          ...node,
          children: node.children || [],
        })),
        organizationSearch,
      ),
    [organizationSearch, organizationsTreeData?.data],
  )

  const filteredGroupsTree = useMemo(
    () =>
      filterTreeByName(
        ((groupsTreeData?.data as TreeNodeLike[]) ?? []).map((node) => ({
          ...node,
          children: node.children || [],
        })),
        groupSearch,
      ),
    [groupSearch, groupsTreeData?.data],
  )

  const organizationsCount = organizationsData?.data?.length ?? 0
  const groupsCount = (organizationsData?.data ?? []).reduce(
    (acc, organization) => acc + Number(organization.groups_count || 0),
    0,
  )
  const selectedOrganizationGroupsCount = groupsData?.data?.length ?? 0
  const organizationMembersCount = organizationMembersData?.data?.length ?? 0
  const groupMembersCount = groupMembersData?.data?.length ?? 0
  const filteredOrganizationMembers = useMemo(() => {
    const rows = organizationMembersData?.data ?? []
    const query = organizationMemberSearch.trim().toLowerCase()
    return rows.filter((member) => {
      const role = (member.role_name || "member") as RoleName
      if (organizationMemberRoleFilter !== "all" && role !== organizationMemberRoleFilter) {
        return false
      }
      if (!query) return true
      const haystack = `${member.user_name || ""} ${member.user_email || ""}`.toLowerCase()
      return haystack.includes(query)
    })
  }, [organizationMemberRoleFilter, organizationMemberSearch, organizationMembersData?.data])

  const filteredGroupMembers = useMemo(() => {
    const rows = groupMembersData?.data ?? []
    const query = groupMemberSearch.trim().toLowerCase()
    return rows.filter((member) => {
      const role = (member.role_name || "member") as RoleName
      if (groupMemberRoleFilter !== "all" && role !== groupMemberRoleFilter) {
        return false
      }
      if (!query) return true
      const haystack = `${member.user_name || ""} ${member.user_email || ""}`.toLowerCase()
      return haystack.includes(query)
    })
  }, [groupMemberRoleFilter, groupMemberSearch, groupMembersData?.data])

  const renderOrganizationTree = (
    nodes: Array<{ id: number; name: string; children?: any[] }>,
    level = 0,
  ): any[] =>
    nodes.flatMap((node) => [
      <Box
        key={`org-tree-${node.id}`}
        pl={4 + level * 18}
        pr={3}
        py={2.5}
        borderTopWidth="1px"
        borderColor="ui.border"
        cursor="pointer"
        bg={selectedOrganizationId === node.id ? selectedNodeBg : "transparent"}
        _hover={{ bg: nodeHoverBg }}
        onClick={() => setSelectedOrganizationId(node.id)}
      >
        <HStack justify="space-between" spacing={3}>
          <HStack spacing={2}>
            <Box
              w="8px"
              h="8px"
              borderRadius="full"
              bg={selectedOrganizationId === node.id ? "ui.main" : "ui.dim"}
            />
            <Text fontWeight={selectedOrganizationId === node.id ? "700" : "600"}>{node.name}</Text>
          </HStack>
          <HStack spacing={1}>
            {!!node.children?.length && (
              <Badge variant="subtle" colorScheme="blue" borderRadius="full">
                {node.children.length}
              </Badge>
            )}
            <IconButton
              aria-label={`Настроить организацию ${node.name}`}
              icon={<FiSettings />}
              size="xs"
              variant="ghost"
              onClick={(event) => {
                event.stopPropagation()
                setSelectedOrganizationId(node.id)
                setShowOrganizationSettings(true)
              }}
            />
          </HStack>
        </HStack>
      </Box>,
      ...(node.children?.length ? renderOrganizationTree(node.children, level + 1) : []),
    ])

  const renderGroupTree = (
    nodes: Array<{ id: number; name: string; children?: any[] }>,
    level = 0,
  ): any[] =>
    nodes.flatMap((node) => [
      <Box
        key={`group-tree-${node.id}`}
        pl={4 + level * 18}
        pr={3}
        py={2.5}
        borderTopWidth="1px"
        borderColor="ui.border"
        cursor="pointer"
        bg={selectedGroupId === node.id ? selectedNodeBg : "transparent"}
        _hover={{ bg: nodeHoverBg }}
        onClick={() => setSelectedGroupId(node.id)}
      >
        <HStack justify="space-between" spacing={3}>
          <HStack spacing={2}>
            <Box
              w="8px"
              h="8px"
              borderRadius="full"
              bg={selectedGroupId === node.id ? "ui.main" : "ui.dim"}
            />
            <Text fontWeight={selectedGroupId === node.id ? "700" : "600"}>{node.name}</Text>
          </HStack>
          <HStack spacing={1}>
            {!!node.children?.length && (
              <Badge variant="subtle" colorScheme="blue" borderRadius="full">
                {node.children.length}
              </Badge>
            )}
            <IconButton
              aria-label={`Настроить группу ${node.name}`}
              icon={<FiSettings />}
              size="xs"
              variant="ghost"
              onClick={(event) => {
                event.stopPropagation()
                setSelectedGroupId(node.id)
                setShowGroupSettings(true)
              }}
            />
          </HStack>
        </HStack>
      </Box>,
      ...(node.children?.length ? renderGroupTree(node.children, level + 1) : []),
    ])

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
              Администрирование структуры
            </Text>
            <Heading mt={1} size="lg" color="white">
              Управление группами
            </Heading>
            <Text mt={2} color="whiteAlpha.900">
              Иерархия организаций и групп, роли и назначение пользователей в одном окне.
            </Text>
          </Box>
          <Badge
            px={3}
            py={1.5}
            borderRadius="full"
            bg="whiteAlpha.300"
            color="white"
            fontSize="sm"
            fontWeight="700"
          >
            {selectedOrganization ? `Орг: ${selectedOrganization.name}` : "Организация не выбрана"}
          </Badge>
        </Flex>
      </Box>

      <SimpleGrid columns={{ base: 1, sm: 2, lg: 4 }} spacing={3} mb={5}>
        <Box borderWidth="1px" borderColor="ui.border" bg={cardBg} borderRadius="12px" p={3} boxShadow="sm">
          <Stat>
            <HStack spacing={2} mb={1}>
              <Icon as={FiBriefcase} color="ui.main" />
              <StatLabel m={0}>Организации</StatLabel>
            </HStack>
            <StatNumber>{organizationsCount}</StatNumber>
          </Stat>
        </Box>
        <Box borderWidth="1px" borderColor="ui.border" bg={cardBg} borderRadius="12px" p={3} boxShadow="sm">
          <Stat>
            <HStack spacing={2} mb={1}>
              <Icon as={FiFolder} color="ui.main" />
              <StatLabel m={0}>Группы (всего)</StatLabel>
            </HStack>
            <StatNumber>{groupsCount}</StatNumber>
          </Stat>
        </Box>
        <Box borderWidth="1px" borderColor="ui.border" bg={cardBg} borderRadius="12px" p={3} boxShadow="sm">
          <Stat>
            <HStack spacing={2} mb={1}>
              <Icon as={FiUsers} color="ui.main" />
              <StatLabel m={0}>Участники организации</StatLabel>
            </HStack>
            <StatNumber>{organizationMembersCount}</StatNumber>
          </Stat>
        </Box>
        <Box borderWidth="1px" borderColor="ui.border" bg={cardBg} borderRadius="12px" p={3} boxShadow="sm">
          <Stat>
            <HStack spacing={2} mb={1}>
              <Icon as={FiLayers} color="ui.main" />
              <StatLabel m={0}>Участники группы</StatLabel>
            </HStack>
            <StatNumber>{groupMembersCount}</StatNumber>
          </Stat>
        </Box>
      </SimpleGrid>

      <Grid templateColumns={{ base: "1fr", xl: "360px 1fr" }} gap={4}>
        <GridItem>
          <Box
            borderWidth="1px"
            borderColor="ui.border"
            borderRadius="12px"
            p={4}
            bgGradient={panelGradient}
            boxShadow="sm"
            mb={4}
          >
            <HStack justify="space-between" mb={showCreateOrganization ? 3 : 0}>
              <Heading size="sm">Создать организацию</Heading>
              <Button
                size="xs"
                variant="subtle"
                leftIcon={showCreateOrganization ? <FiChevronUp /> : <FiPlus />}
                onClick={() => setShowCreateOrganization((prev) => !prev)}
              >
                {showCreateOrganization ? "Скрыть" : "Показать"}
              </Button>
            </HStack>
            <Collapse in={showCreateOrganization} animateOpacity>
              <HStack mb={3} spacing={2} flexWrap="wrap">
                <Button
                  size="xs"
                  variant="subtle"
                  onClick={() =>
                    setOrganizationForm((prev) => ({
                      ...prev,
                      parent_organization_id: selectedOrganizationId ? String(selectedOrganizationId) : "",
                    }))
                  }
                  isDisabled={!selectedOrganizationId}
                >
                  Сделать дочерней к выбранной
                </Button>
                <Button
                  size="xs"
                  variant="subtle"
                  onClick={() =>
                    setOrganizationForm({
                      name: "",
                      code: "",
                      description: "",
                      parent_organization_id: "",
                    })
                  }
                >
                  Очистить форму
                </Button>
              </HStack>
              <VStack spacing={3} align="stretch">
                <FormControl isRequired>
                  <FormLabel>Название</FormLabel>
                  <Input
                    value={organizationForm.name}
                    onChange={(e) => setOrganizationForm((prev) => ({ ...prev, name: e.target.value }))}
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Код</FormLabel>
                  <Input
                    value={organizationForm.code}
                    onChange={(e) => setOrganizationForm((prev) => ({ ...prev, code: e.target.value }))}
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Описание</FormLabel>
                  <Textarea
                    value={organizationForm.description}
                    minH="84px"
                    resize="vertical"
                    onChange={(e) =>
                      setOrganizationForm((prev) => ({ ...prev, description: e.target.value }))
                    }
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Родительская организация</FormLabel>
                  <Select
                    value={organizationForm.parent_organization_id}
                    onChange={(e) =>
                      setOrganizationForm((prev) => ({
                        ...prev,
                        parent_organization_id: e.target.value,
                      }))
                    }
                  >
                    <option value="">Нет (корневой уровень)</option>
                    {organizationParentOptions.map((option) => (
                      <option key={`org-parent-${option.id}`} value={option.id}>
                        {option.label}
                      </option>
                    ))}
                  </Select>
                </FormControl>
                <Button
                  onClick={() => createOrganizationMutation.mutate()}
                  isLoading={createOrganizationMutation.isPending}
                  isDisabled={!organizationForm.name.trim()}
                >
                  Создать организацию
                </Button>
              </VStack>
            </Collapse>
          </Box>

          <Box
            borderWidth="1px"
            borderColor="ui.border"
            borderRadius="12px"
            bgGradient={panelGradientAlt}
            boxShadow="sm"
            overflow="hidden"
          >
            <HStack px={4} py={3} borderBottomWidth="1px" borderColor="ui.border" justify="space-between">
              <HStack spacing={2}>
                <Text fontWeight="700">Организации</Text>
                <Badge borderRadius="full" colorScheme="blue" variant="subtle">
                  {organizationsCount}
                </Badge>
              </HStack>
              <Button
                size="xs"
                variant="subtle"
                leftIcon={showCreateOrganization ? <FiChevronUp /> : <FiPlus />}
                onClick={() => setShowCreateOrganization((prev) => !prev)}
              >
                {showCreateOrganization ? "Скрыть создание" : "Создать организацию"}
              </Button>
            </HStack>
            <Box px={4} py={3} borderBottomWidth="1px" borderColor="ui.border">
              <Input
                placeholder="Поиск по организациям"
                value={organizationSearch}
                onChange={(event) => setOrganizationSearch(event.target.value)}
              />
            </Box>
            <VStack align="stretch" spacing={0}>
              {!organizationsLoading && !(organizationsTreeData?.data as any[])?.length && (
                <Text px={4} py={4} color="ui.muted">
                  Организаций пока нет.
                </Text>
              )}
              {!organizationsLoading &&
                Boolean((organizationsTreeData?.data as any[])?.length) &&
                !filteredOrganizationTree.length && (
                  <Text px={4} py={4} color="ui.muted">
                    По запросу ничего не найдено.
                  </Text>
                )}
              {organizationsLoading && (
                <Text px={4} py={4} color="ui.muted">
                  Загрузка...
                </Text>
              )}
              {renderOrganizationTree(filteredOrganizationTree)}
            </VStack>
          </Box>
        </GridItem>

        <GridItem>
          <Box
            borderWidth="1px"
            borderColor="ui.border"
            borderRadius="12px"
            p={4}
            bgGradient={panelGradient}
            boxShadow="sm"
            mb={4}
          >
            <Heading size="sm" mb={2}>
              Схема работы
            </Heading>
            <SimpleGrid columns={{ base: 1, md: 3 }} spacing={3}>
              <Box borderWidth="1px" borderColor="ui.border" borderRadius="10px" p={3} bg={cardBg}>
                <Text fontWeight="700" color="ui.main" mb={1}>
                  1. Выберите организацию
                </Text>
                <Text fontSize="sm" color="ui.muted">
                  Слева выберите ветку в дереве, чтобы привязать группы и участников к нужному блоку.
                </Text>
              </Box>
              <Box borderWidth="1px" borderColor="ui.border" borderRadius="10px" p={3} bg={cardBg}>
                <Text fontWeight="700" color="ui.main" mb={1}>
                  2. Настройте структуру
                </Text>
                <Text fontSize="sm" color="ui.muted">
                  На вкладке «Структура» создавайте/редактируйте группы, иерархию и параметры узлов.
                </Text>
              </Box>
              <Box borderWidth="1px" borderColor="ui.border" borderRadius="10px" p={3} bg={cardBg}>
                <Text fontWeight="700" color="ui.main" mb={1}>
                  3. Назначьте роли
                </Text>
                <Text fontSize="sm" color="ui.muted">
                  Выберите группу в дереве и ниже в разделе «Участники и роли» назначайте директор/руководитель/участник.
                </Text>
              </Box>
            </SimpleGrid>
          </Box>

          <Tabs variant="enclosed-colored" colorScheme="blue" isLazy>
            <TabList>
              <Tab>Структура и участники</Tab>
            </TabList>
            <TabPanels>
              <TabPanel px={0} pt={4}>
                <Grid templateColumns={{ base: "1fr", xl: "1fr 1fr" }} gap={4} mb={4}>
                  <GridItem>
                    <Box
                      borderWidth="1px"
                      borderColor="ui.border"
                      borderRadius="12px"
                      p={4}
                      bgGradient={panelGradient}
                      boxShadow="sm"
                    >
                      <HStack justify="space-between" mb={showOrganizationSettings ? 3 : 0}>
                        <Heading size="sm">Настройки организации</Heading>
                        <Button
                          size="xs"
                          variant="subtle"
                          leftIcon={showOrganizationSettings ? <FiChevronUp /> : <FiSettings />}
                          onClick={() =>
                            setShowOrganizationSettings((prev) => !prev)
                          }
                          isDisabled={!selectedOrganization}
                        >
                          {showOrganizationSettings ? "Скрыть" : "Открыть"}
                        </Button>
                      </HStack>
                      <Collapse in={showOrganizationSettings} animateOpacity>
                        {selectedOrganization ? (
                          <VStack spacing={3} align="stretch">
                            <FormControl isRequired>
                              <FormLabel>Название</FormLabel>
                              <Input
                                value={organizationEditForm.name}
                                onChange={(e) =>
                                  setOrganizationEditForm((prev) => ({ ...prev, name: e.target.value }))
                                }
                              />
                            </FormControl>
                            <FormControl>
                              <FormLabel>Код</FormLabel>
                              <Input
                                value={organizationEditForm.code}
                                onChange={(e) =>
                                  setOrganizationEditForm((prev) => ({ ...prev, code: e.target.value }))
                                }
                              />
                            </FormControl>
                            <FormControl>
                              <FormLabel>Описание</FormLabel>
                              <Textarea
                                value={organizationEditForm.description}
                                minH="84px"
                                resize="vertical"
                                onChange={(e) =>
                                  setOrganizationEditForm((prev) => ({
                                    ...prev,
                                    description: e.target.value,
                                  }))
                                }
                              />
                            </FormControl>
                            <FormControl>
                              <FormLabel>Родительская организация</FormLabel>
                              <Select
                                value={organizationEditForm.parent_organization_id}
                                onChange={(e) =>
                                  setOrganizationEditForm((prev) => ({
                                    ...prev,
                                    parent_organization_id: e.target.value,
                                  }))
                                }
                              >
                                <option value="">Нет (корневой уровень)</option>
                                {organizationParentOptions
                                  .filter((option) => option.id !== selectedOrganizationId)
                                  .map((option) => (
                                    <option key={`org-edit-parent-${option.id}`} value={option.id}>
                                      {option.label}
                                    </option>
                                  ))}
                              </Select>
                            </FormControl>
                            <HStack spacing={2}>
                              <Button
                                onClick={() => updateOrganizationMutation.mutate()}
                                isLoading={updateOrganizationMutation.isPending}
                                isDisabled={!organizationEditForm.name.trim()}
                              >
                                Сохранить
                              </Button>
                              <Button
                                colorScheme="red"
                                variant="outline"
                                onClick={() => {
                                  if (!selectedOrganizationId) return
                                  if (!window.confirm("Удалить выбранную организацию?")) return
                                  deleteOrganizationMutation.mutate()
                                }}
                                isLoading={deleteOrganizationMutation.isPending}
                              >
                                Удалить
                              </Button>
                            </HStack>
                          </VStack>
                        ) : (
                          <Text color="ui.muted">Выберите организацию в дереве слева</Text>
                        )}
                      </Collapse>
                    </Box>
                  </GridItem>

                  <GridItem>
                    <Box
                      borderWidth="1px"
                      borderColor="ui.border"
                      borderRadius="12px"
                      p={4}
                      bgGradient={panelGradient}
                      boxShadow="sm"
                    >
                      <HStack justify="space-between" mb={showCreateGroup ? 3 : 0}>
                        <Heading size="sm">Создать группу</Heading>
                        <Button
                          size="xs"
                          variant="subtle"
                          leftIcon={showCreateGroup ? <FiChevronUp /> : <FiPlus />}
                          onClick={() => setShowCreateGroup((prev) => !prev)}
                          isDisabled={!selectedOrganization}
                        >
                          {showCreateGroup ? "Скрыть" : "Открыть"}
                        </Button>
                      </HStack>
                      <Collapse in={showCreateGroup} animateOpacity>
                        <HStack mb={3} spacing={2} flexWrap="wrap">
                          <Button
                            size="xs"
                            variant="subtle"
                            onClick={() =>
                              setGroupForm((prev) => ({
                                ...prev,
                                parent_group_id: selectedGroupId ? String(selectedGroupId) : "",
                              }))
                            }
                            isDisabled={!selectedGroupId}
                          >
                            Сделать подгруппой выбранной
                          </Button>
                          <Button
                            size="xs"
                            variant="subtle"
                            onClick={() =>
                              setGroupForm({
                                name: "",
                                code: "",
                                description: "",
                                parent_group_id: "",
                              })
                            }
                          >
                            Очистить форму
                          </Button>
                        </HStack>
                        <VStack spacing={3} align="stretch">
                        <FormControl isRequired>
                          <FormLabel>Название группы</FormLabel>
                          <Input
                            value={groupForm.name}
                            onChange={(e) => setGroupForm((prev) => ({ ...prev, name: e.target.value }))}
                          />
                        </FormControl>
                        <FormControl>
                          <FormLabel>Код</FormLabel>
                          <Input
                            value={groupForm.code}
                            onChange={(e) => setGroupForm((prev) => ({ ...prev, code: e.target.value }))}
                          />
                        </FormControl>
                        <FormControl>
                          <FormLabel>Описание</FormLabel>
                          <Textarea
                            value={groupForm.description}
                            minH="84px"
                            resize="vertical"
                            onChange={(e) =>
                              setGroupForm((prev) => ({ ...prev, description: e.target.value }))
                            }
                          />
                        </FormControl>
                        <FormControl>
                          <FormLabel>Родительская группа</FormLabel>
                          <Select
                            value={groupForm.parent_group_id}
                            onChange={(e) =>
                              setGroupForm((prev) => ({ ...prev, parent_group_id: e.target.value }))
                            }
                          >
                            <option value="">Нет (верхний уровень)</option>
                            {groupParentOptions.map((option) => (
                              <option key={`group-parent-${option.id}`} value={option.id}>
                                {option.label}
                              </option>
                            ))}
                          </Select>
                        </FormControl>
                          <Button
                            onClick={() => createGroupMutation.mutate()}
                            isLoading={createGroupMutation.isPending}
                            isDisabled={!selectedOrganizationId || !groupForm.name.trim()}
                          >
                            Создать группу
                          </Button>
                        </VStack>
                      </Collapse>
                    </Box>
                  </GridItem>
                </Grid>

                <Grid
                  templateColumns={{
                    base: "1fr",
                    xl: showOrganizationMembersSection ? "1fr 1fr" : "1fr",
                  }}
                  gap={4}
                >
                  <GridItem>
                    <Box
                      borderWidth="1px"
                      borderColor="ui.border"
                      borderRadius="12px"
                      bgGradient={panelGradientAlt}
                      boxShadow="sm"
                      overflow="hidden"
                    >
                      <HStack px={4} py={3} borderBottomWidth="1px" borderColor="ui.border" justify="space-between">
                        <HStack spacing={2}>
                          <Text fontWeight="700">Список групп</Text>
                          <Badge borderRadius="full" colorScheme="blue" variant="subtle">
                            {selectedOrganizationGroupsCount}
                          </Badge>
                        </HStack>
                        <Button
                          size="xs"
                          variant="subtle"
                          leftIcon={showCreateGroup ? <FiChevronUp /> : <FiPlus />}
                          onClick={() => setShowCreateGroup((prev) => !prev)}
                          isDisabled={!selectedOrganization}
                        >
                          {showCreateGroup ? "Скрыть создание" : "Создать группу"}
                        </Button>
                      </HStack>
                      <Box px={4} py={3} borderBottomWidth="1px" borderColor="ui.border">
                        <Input
                          placeholder="Поиск по группам"
                          value={groupSearch}
                          onChange={(event) => setGroupSearch(event.target.value)}
                        />
                      </Box>
                      <VStack align="stretch" spacing={0}>
                        {groupsLoading && (
                          <Text px={4} py={4} color="ui.muted">
                            Загрузка...
                          </Text>
                        )}
                        {!groupsLoading && !(groupsData?.data ?? []).length && (
                          <Text px={4} py={4} color="ui.muted">
                            В выбранной организации пока нет групп.
                          </Text>
                        )}
                        {!groupsLoading && Boolean((groupsData?.data ?? []).length) && !filteredGroupsTree.length && (
                          <Text px={4} py={4} color="ui.muted">
                            По запросу ничего не найдено.
                          </Text>
                        )}
                        {renderGroupTree(filteredGroupsTree)}
                      </VStack>
                    </Box>
                  </GridItem>

                  <GridItem>
                    <Box
                      borderWidth="1px"
                      borderColor="ui.border"
                      borderRadius="12px"
                      p={4}
                      bgGradient={panelGradient}
                      boxShadow="sm"
                    >
                      <HStack justify="space-between" mb={showGroupSettings ? 3 : 0}>
                        <Heading size="sm">Настройки группы</Heading>
                        <Button
                          size="xs"
                          variant="subtle"
                          leftIcon={showGroupSettings ? <FiChevronUp /> : <FiSettings />}
                          onClick={() => setShowGroupSettings((prev) => !prev)}
                          isDisabled={!selectedGroup}
                        >
                          {showGroupSettings ? "Скрыть" : "Открыть"}
                        </Button>
                      </HStack>
                      <Collapse in={showGroupSettings} animateOpacity>
                        {selectedGroup ? (
                          <VStack spacing={3} align="stretch">
                          <FormControl isRequired>
                            <FormLabel>Название</FormLabel>
                            <Input
                              value={groupEditForm.name}
                              onChange={(e) =>
                                setGroupEditForm((prev) => ({ ...prev, name: e.target.value }))
                              }
                            />
                          </FormControl>
                          <FormControl>
                            <FormLabel>Код</FormLabel>
                            <Input
                              value={groupEditForm.code}
                              onChange={(e) =>
                                setGroupEditForm((prev) => ({ ...prev, code: e.target.value }))
                              }
                            />
                          </FormControl>
                          <FormControl>
                            <FormLabel>Описание</FormLabel>
                            <Textarea
                              value={groupEditForm.description}
                              minH="84px"
                              resize="vertical"
                              onChange={(e) =>
                                setGroupEditForm((prev) => ({ ...prev, description: e.target.value }))
                              }
                            />
                          </FormControl>
                          <FormControl>
                            <FormLabel>Родительская группа</FormLabel>
                            <Select
                              value={groupEditForm.parent_group_id}
                              onChange={(e) =>
                                setGroupEditForm((prev) => ({
                                  ...prev,
                                  parent_group_id: e.target.value,
                                }))
                              }
                            >
                              <option value="">Нет (верхний уровень)</option>
                              {groupParentOptions
                                .filter((option) => option.id !== selectedGroupId)
                                .map((option) => (
                                  <option key={`group-edit-parent-${option.id}`} value={option.id}>
                                    {option.label}
                                  </option>
                                ))}
                            </Select>
                          </FormControl>
                          <HStack spacing={2}>
                            <Button
                              onClick={() => updateGroupMutation.mutate()}
                              isLoading={updateGroupMutation.isPending}
                              isDisabled={!groupEditForm.name.trim()}
                            >
                              Сохранить
                            </Button>
                            <Button
                              colorScheme="red"
                              variant="outline"
                              onClick={() => {
                                if (!selectedGroupId) return
                                if (!window.confirm("Удалить выбранную группу?")) return
                                deleteGroupMutation.mutate()
                              }}
                              isLoading={deleteGroupMutation.isPending}
                            >
                              Удалить
                            </Button>
                          </HStack>
                          </VStack>
                        ) : (
                          <Text color="ui.muted">Выберите группу в дереве</Text>
                        )}
                      </Collapse>
                    </Box>
                  </GridItem>
                </Grid>
                <Box
                  borderWidth="1px"
                  borderColor="ui.border"
                  borderRadius="12px"
                  p={4}
                  bgGradient={panelGradient}
                  boxShadow="sm"
                  mt={4}
                  mb={4}
                >
                  <HStack justify="space-between" flexWrap="wrap" gap={2}>
                    <Box>
                      <Heading size="sm" mb={1}>
                        Участники и роли
                      </Heading>
                      <Text fontSize="sm" color="ui.muted">
                        Сначала выберите группу в дереве, затем назначайте роли участников внутри выбранной группы.
                      </Text>
                    </Box>
                    <HStack spacing={2} flexWrap="wrap">
                      <Badge colorScheme="purple" variant="subtle" borderRadius="full" px={3} py={1}>
                        Организация: {selectedOrganization?.name || "не выбрана"}
                      </Badge>
                      <Badge colorScheme="blue" variant="subtle" borderRadius="full" px={3} py={1}>
                        Группа: {selectedGroup?.name || "не выбрана"}
                      </Badge>
                      <Button
                        size="xs"
                        variant="subtle"
                        onClick={() =>
                          setShowOrganizationMembersSection((prev) => !prev)
                        }
                      >
                        {showOrganizationMembersSection
                          ? "Скрыть участников организации"
                          : "Показать участников организации (доп.)"}
                      </Button>
                    </HStack>
                  </HStack>
                </Box>
                <Grid templateColumns={{ base: "1fr", xl: "1fr 1fr" }} gap={4}>
                  <GridItem>
                    <Collapse in={showOrganizationMembersSection} animateOpacity>
                    <Box
                      borderWidth="1px"
                      borderColor="ui.border"
                      borderRadius="12px"
                      p={4}
                      bgGradient={panelGradient}
                      boxShadow="sm"
                    >
                      <Heading size="sm" mb={1}>
                        Участники организации (дополнительно)
                      </Heading>
                      <Text fontSize="sm" color="ui.muted" mb={3}>
                        {selectedOrganization ? selectedOrganization.name : "Выберите организацию"}
                      </Text>
                      <Grid templateColumns={{ base: "1fr", md: "1.4fr 1fr auto" }} gap={2} mb={3}>
                        <FormControl>
                          <FormLabel>Поиск участника</FormLabel>
                          <Input
                            value={organizationMemberSearch}
                            onChange={(event) => setOrganizationMemberSearch(event.target.value)}
                            placeholder="ФИО или email"
                          />
                        </FormControl>
                        <FormControl>
                          <FormLabel>Фильтр роли</FormLabel>
                          <Select
                            value={organizationMemberRoleFilter}
                            onChange={(event) =>
                              setOrganizationMemberRoleFilter(event.target.value as "all" | RoleName)
                            }
                          >
                            <option value="all">Все роли</option>
                            {ROLE_OPTIONS.map((role) => (
                              <option key={`organization-member-filter-${role.value}`} value={role.value}>
                                {role.label}
                              </option>
                            ))}
                          </Select>
                        </FormControl>
                        <HStack mt={{ base: 0, md: 8 }} justify={{ base: "start", md: "end" }}>
                          <Badge borderRadius="full" colorScheme="blue" variant="subtle" px={2.5} py={1}>
                            Показано: {filteredOrganizationMembers.length}
                          </Badge>
                        </HStack>
                      </Grid>

                      <Grid templateColumns={{ base: "1fr", md: "1fr 1.4fr 1fr auto" }} gap={2} mb={3}>
                        <FormControl>
                          <FormLabel>Поиск пользователя</FormLabel>
                          <Input
                            value={organizationUserSearch}
                            onChange={(event) => setOrganizationUserSearch(event.target.value)}
                            placeholder="ФИО или email"
                          />
                        </FormControl>
                        <FormControl>
                          <FormLabel>Пользователь</FormLabel>
                          <Select
                            value={organizationMemberForm.user_id}
                            onChange={(e) =>
                              setOrganizationMemberForm((prev) => ({ ...prev, user_id: e.target.value }))
                            }
                          >
                            <option value="">Выберите пользователя</option>
                            {filteredOrganizationUsersOptions.map((user) => (
                              <option key={`org-member-${user.id}`} value={user.id}>
                                {user.full_name || user.email} ({user.email})
                              </option>
                            ))}
                          </Select>
                        </FormControl>
                        <FormControl>
                          <FormLabel>Роль</FormLabel>
                          <Select
                            value={organizationMemberForm.role_name}
                            onChange={(e) =>
                              setOrganizationMemberForm((prev) => ({
                                ...prev,
                                role_name: e.target.value as RoleName,
                              }))
                            }
                          >
                            {ROLE_OPTIONS.map((role) => (
                              <option key={`org-role-${role.value}`} value={role.value}>
                                {role.label}
                              </option>
                            ))}
                          </Select>
                        </FormControl>
                        <Button
                          mt={{ base: 0, md: 8 }}
                          onClick={() => addOrganizationMemberMutation.mutate()}
                          isLoading={addOrganizationMemberMutation.isPending}
                          isDisabled={!selectedOrganizationId || !organizationMemberForm.user_id}
                        >
                          Добавить
                        </Button>
                      </Grid>

                      <VStack align="stretch" spacing={2} maxH="380px" overflowY="auto">
                        {organizationMembersLoading && <Text color="ui.muted">Загрузка...</Text>}
                        {!organizationMembersLoading && !(organizationMembersData?.data ?? []).length && (
                          <Text color="ui.muted">Участников пока нет</Text>
                        )}
                        {!organizationMembersLoading &&
                          Boolean((organizationMembersData?.data ?? []).length) &&
                          !filteredOrganizationMembers.length && (
                            <Text color="ui.muted">По выбранным фильтрам участников нет</Text>
                          )}
                        {filteredOrganizationMembers.map((member) => (
                          <Box
                            key={`org-member-row-${member.user_id}`}
                            borderWidth="1px"
                            borderColor="ui.border"
                            borderRadius="10px"
                            borderLeftWidth="4px"
                            borderLeftColor={member.is_active ? "ui.success" : "ui.border"}
                            bg={member.is_active ? activeMemberBg : inactiveMemberBg}
                            p={3}
                          >
                            <HStack justify="space-between" align="start" mb={2}>
                              <Box>
                                <Text fontWeight="600">{member.user_name || member.user_email}</Text>
                                <Text fontSize="sm" color="ui.muted">
                                  {member.user_email}
                                </Text>
                              </Box>
                              <Badge colorScheme={member.is_active ? "green" : "gray"}>
                                {member.is_active ? "Активен" : "Неактивен"}
                              </Badge>
                            </HStack>
                            <HStack spacing={2}>
                              <Select
                                size="sm"
                                value={organizationMemberRoles[member.user_id] || "member"}
                                onChange={(e) =>
                                  setOrganizationMemberRoles((prev) => ({
                                    ...prev,
                                    [member.user_id]: e.target.value as RoleName,
                                  }))
                                }
                              >
                                {ROLE_OPTIONS.map((role) => (
                                  <option key={`org-row-role-${member.user_id}-${role.value}`} value={role.value}>
                                    {role.label}
                                  </option>
                                ))}
                              </Select>
                              <Button
                                size="sm"
                                onClick={() =>
                                  updateOrganizationMemberMutation.mutate({
                                    userId: member.user_id,
                                    roleName: organizationMemberRoles[member.user_id] || "member",
                                  })
                                }
                                isLoading={
                                  updateOrganizationMemberMutation.isPending &&
                                  updateOrganizationMemberMutation.variables?.userId === member.user_id
                                }
                              >
                                Сохранить роль
                              </Button>
                              <Button
                                size="sm"
                                colorScheme="red"
                                variant="outline"
                                onClick={() => removeOrganizationMemberMutation.mutate(member.user_id)}
                                isLoading={
                                  removeOrganizationMemberMutation.isPending &&
                                  removeOrganizationMemberMutation.variables === member.user_id
                                }
                              >
                                Удалить
                              </Button>
                            </HStack>
                          </Box>
                        ))}
                      </VStack>
                    </Box>
                    </Collapse>
                  </GridItem>

                  <GridItem>
                    <Box
                      borderWidth="1px"
                      borderColor="ui.border"
                      borderRadius="12px"
                      p={4}
                      bgGradient={panelGradient}
                      boxShadow="sm"
                    >
                      <HStack justify="space-between" align="start" mb={3} flexWrap="wrap">
                        <Box>
                          <Heading size="sm" mb={1}>
                            Участники и роли группы
                          </Heading>
                          <Text fontSize="sm" color="ui.muted">
                            {selectedGroup
                              ? `Текущая группа: ${selectedGroup.name}`
                              : "Выберите группу в дереве слева"}
                          </Text>
                        </Box>
                        {selectedGroup ? (
                          <Badge colorScheme="blue" variant="subtle" borderRadius="full" px={3} py={1}>
                            ID группы: {selectedGroup.id}
                          </Badge>
                        ) : null}
                      </HStack>
                      <Grid templateColumns={{ base: "1fr", md: "1.4fr 1fr auto" }} gap={2} mb={3}>
                        <FormControl>
                          <FormLabel>Поиск участника</FormLabel>
                          <Input
                            value={groupMemberSearch}
                            onChange={(event) => setGroupMemberSearch(event.target.value)}
                            placeholder="ФИО или email"
                          />
                        </FormControl>
                        <FormControl>
                          <FormLabel>Фильтр роли</FormLabel>
                          <Select
                            value={groupMemberRoleFilter}
                            onChange={(event) => setGroupMemberRoleFilter(event.target.value as "all" | RoleName)}
                          >
                            <option value="all">Все роли</option>
                            {ROLE_OPTIONS.map((role) => (
                              <option key={`group-member-filter-${role.value}`} value={role.value}>
                                {role.label}
                              </option>
                            ))}
                          </Select>
                        </FormControl>
                        <HStack mt={{ base: 0, md: 8 }} justify={{ base: "start", md: "end" }}>
                          <Badge borderRadius="full" colorScheme="blue" variant="subtle" px={2.5} py={1}>
                            Показано: {filteredGroupMembers.length}
                          </Badge>
                        </HStack>
                      </Grid>

                      <Grid
                        templateColumns={{ base: "1fr", lg: "1fr 1.35fr 0.95fr auto" }}
                        alignItems="end"
                        gap={2}
                        mb={3}
                      >
                        <FormControl>
                          <FormLabel mb={1}>Поиск пользователя</FormLabel>
                          <Input
                            value={groupUserSearch}
                            onChange={(event) => setGroupUserSearch(event.target.value)}
                            placeholder="ФИО или email"
                          />
                        </FormControl>
                        <FormControl>
                          <FormLabel mb={1}>Пользователь</FormLabel>
                          <Select
                            value={groupMemberForm.user_id}
                            onChange={(e) =>
                              setGroupMemberForm((prev) => ({ ...prev, user_id: e.target.value }))
                            }
                          >
                            <option value="">Выберите пользователя</option>
                            {filteredGroupUsersOptions.map((user) => (
                              <option key={`group-member-${user.id}`} value={user.id}>
                                {user.full_name || user.email}
                              </option>
                            ))}
                          </Select>
                        </FormControl>
                        <FormControl>
                          <FormLabel mb={1}>Роль</FormLabel>
                          <Select
                            value={groupMemberForm.role_name}
                            onChange={(e) =>
                              setGroupMemberForm((prev) => ({
                                ...prev,
                                role_name: e.target.value as RoleName,
                              }))
                            }
                          >
                            {ROLE_OPTIONS.map((role) => (
                              <option key={`group-role-${role.value}`} value={role.value}>
                                {role.label}
                              </option>
                            ))}
                          </Select>
                        </FormControl>
                        <Button
                          onClick={() => addGroupMemberMutation.mutate()}
                          isLoading={addGroupMemberMutation.isPending}
                          isDisabled={!selectedGroupId || !groupMemberForm.user_id}
                        >
                          Добавить
                        </Button>
                      </Grid>

                      <VStack align="stretch" spacing={2} maxH="380px" overflowY="auto">
                        {groupMembersLoading && <Text color="ui.muted">Загрузка...</Text>}
                        {!groupMembersLoading && !(groupMembersData?.data ?? []).length && (
                          <Text color="ui.muted">Участников пока нет</Text>
                        )}
                        {!groupMembersLoading &&
                          Boolean((groupMembersData?.data ?? []).length) &&
                          !filteredGroupMembers.length && (
                            <Text color="ui.muted">По выбранным фильтрам участников нет</Text>
                          )}
                        {filteredGroupMembers.map((member) => (
                          <Box
                            key={`group-member-row-${member.user_id}`}
                            borderWidth="1px"
                            borderColor="ui.border"
                            borderRadius="10px"
                            borderLeftWidth="4px"
                            borderLeftColor={member.is_active ? "ui.success" : "ui.border"}
                            bg={member.is_active ? activeMemberBg : inactiveMemberBg}
                            p={3}
                          >
                            <HStack justify="space-between" align="start" mb={2}>
                              <Box>
                                <Text fontWeight="600">{member.user_name || member.user_email}</Text>
                                <Text fontSize="sm" color="ui.muted">
                                  {member.user_email}
                                </Text>
                              </Box>
                              <Badge colorScheme={member.is_active ? "green" : "gray"}>
                                {member.is_active ? "Активен" : "Неактивен"}
                              </Badge>
                            </HStack>
                            <HStack spacing={2}>
                              <Select
                                size="sm"
                                value={groupMemberRoles[member.user_id] || "member"}
                                onChange={(e) =>
                                  setGroupMemberRoles((prev) => ({
                                    ...prev,
                                    [member.user_id]: e.target.value as RoleName,
                                  }))
                                }
                              >
                                {ROLE_OPTIONS.map((role) => (
                                  <option key={`group-row-role-${member.user_id}-${role.value}`} value={role.value}>
                                    {role.label}
                                  </option>
                                ))}
                              </Select>
                              <Button
                                size="sm"
                                onClick={() =>
                                  updateGroupMemberMutation.mutate({
                                    userId: member.user_id,
                                    roleName: groupMemberRoles[member.user_id] || "member",
                                  })
                                }
                                isLoading={
                                  updateGroupMemberMutation.isPending &&
                                  updateGroupMemberMutation.variables?.userId === member.user_id
                                }
                              >
                                Сохранить роль
                              </Button>
                              <Button
                                size="sm"
                                colorScheme="red"
                                variant="outline"
                                onClick={() => removeGroupMemberMutation.mutate(member.user_id)}
                                isLoading={
                                  removeGroupMemberMutation.isPending &&
                                  removeGroupMemberMutation.variables === member.user_id
                                }
                              >
                                Удалить
                              </Button>
                            </HStack>
                            <Text mt={2} fontSize="xs" color="ui.muted">
                              Текущая роль: {roleLabel(member.role_name)}
                            </Text>
                          </Box>
                        ))}
                      </VStack>
                    </Box>
                  </GridItem>
                </Grid>
              </TabPanel>
            </TabPanels>
          </Tabs>
        </GridItem>
      </Grid>
    </Container>
  )
}
