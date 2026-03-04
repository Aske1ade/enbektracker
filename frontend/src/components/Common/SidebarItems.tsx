import { Box, Flex, Icon, Text } from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import {
  FiActivity,
  FiBarChart2,
  FiBookOpen,
  FiCalendar,
  FiClipboard,
  FiFolder,
  FiGrid,
  FiLayers,
  FiSettings,
} from "react-icons/fi"

import type { UserPublic } from "../../client"
import { trackerApi } from "../../services/trackerApi"

type SidebarItem = {
  icon: typeof FiGrid
  title: string
  path: string
}

const baseItems: SidebarItem[] = [
  { icon: FiGrid, title: "Дашборды", path: "/dashboards" },
  { icon: FiClipboard, title: "Задачи", path: "/tasks" },
  { icon: FiCalendar, title: "Календарь", path: "/calendar" },
]

const projectsItem: SidebarItem = { icon: FiFolder, title: "Проекты", path: "/projects" }
const reportsItem: SidebarItem = { icon: FiBarChart2, title: "Отчёты", path: "/reports" }

const leadershipItems: SidebarItem[] = [
  { icon: FiLayers, title: "Управление группами", path: "/blocks" },
  {
    icon: FiBookOpen,
    title: "Справка по дисциплине",
    path: "/discipline-help",
  },
]

const settingsItem: SidebarItem = {
  icon: FiSettings,
  title: "Настройки",
  path: "/settings",
}

const adminItem: SidebarItem = {
  icon: FiActivity,
  title: "Администрирование",
  path: "/admin",
}

interface SidebarItemsProps {
  onClose?: () => void
}

const SidebarItems = ({ onClose }: SidebarItemsProps) => {
  const { data: currentUser } = useQuery({
    queryKey: ["currentUser"],
    queryFn: () => trackerApi.getCurrentUser(),
    retry: false,
  })
  const { data: accessibleProjectsMeta } = useQuery({
    queryKey: ["sidebar-project-access"],
    queryFn: () =>
      trackerApi.listProjects({
        page: 1,
        page_size: 1,
      }),
    retry: false,
  })

  const systemRole = normalizeSystemRole(currentUser)
  const isLeadership =
    currentUser?.is_superuser || systemRole === "system_admin"
  const isAdmin = currentUser?.is_superuser || systemRole === "system_admin"
  const canSeeProjects =
    isLeadership || Number(accessibleProjectsMeta?.count || 0) > 0

  const finalItems = isLeadership
    ? [
        ...baseItems,
        ...(canSeeProjects ? [projectsItem] : []),
        reportsItem,
        ...leadershipItems,
        ...(isAdmin ? [adminItem] : []),
        settingsItem,
      ]
    : [...baseItems, ...(canSeeProjects ? [projectsItem] : []), settingsItem]

  const listItems = finalItems.map(({ icon, title, path }) => (
    <Flex
      as={Link}
      to={path}
      w="100%"
      px={3}
      py={2.5}
      key={title}
      activeProps={{
        style: {
          background: "#E7ECF3",
          borderRadius: "6px",
          borderLeft: "3px solid #1E3A5F",
        },
      }}
      color="ui.darkSlate"
      onClick={onClose}
      borderRadius="6px"
      _hover={{ bg: "ui.secondary" }}
    >
      <Icon as={icon} alignSelf="center" boxSize={4} />
      <Text ml={2} fontSize="sm" fontWeight="500">
        {title}
      </Text>
    </Flex>
  ))

  return (
    <Box display="grid" gap={1}>
      {listItems}
    </Box>
  )
}

export default SidebarItems

function normalizeSystemRole(
  user: (UserPublic & { system_role?: string | null }) | undefined,
): "system_admin" | "user" {
  const role = (user?.system_role || "").toLowerCase()
  if (user?.is_superuser) return "system_admin"
  if (role === "system_admin" || role === "admin" || role === "manager") {
    return "system_admin"
  }
  return "user"
}
