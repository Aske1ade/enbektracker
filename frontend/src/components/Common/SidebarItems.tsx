import { Box, Flex, Icon, Text, useColorModeValue } from "@chakra-ui/react"
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
  { icon: FiClipboard, title: "Задачи", path: "/tasks" },
  { icon: FiCalendar, title: "Календарь", path: "/calendar" },
]

const dashboardsItem: SidebarItem = {
  icon: FiGrid,
  title: "Дашборды",
  path: "/dashboards",
}
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

  const systemRole = normalizeSystemRole(currentUser)
  const isLeadership =
    currentUser?.is_superuser || systemRole === "system_admin"
  const isAdmin = currentUser?.is_superuser || systemRole === "system_admin"

  const activeBackground = useColorModeValue(
    "#E7ECF3",
    "rgba(15, 23, 42, 0.9)",
  )
  const activeBorderLeft = useColorModeValue(
    "3px solid #1E3A5F",
    "3px solid #38BDF8",
  )
  const hoverBackground = useColorModeValue("ui.secondary", "rgba(30, 64, 175, 0.65)")
  const itemTextColor = useColorModeValue("ui.darkSlate", "#E5E7EB")

  const finalItems = isLeadership
    ? [
        ...baseItems,
        projectsItem,
        dashboardsItem,
        reportsItem,
        ...leadershipItems,
        ...(isAdmin ? [adminItem] : []),
        settingsItem,
      ]
    : [
        ...baseItems,
        projectsItem,
        dashboardsItem,
        settingsItem,
      ]

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
          background: activeBackground,
          borderRadius: "6px",
          borderLeft: activeBorderLeft,
        },
      }}
      color={itemTextColor}
      onClick={onClose}
      borderRadius="6px"
      _hover={{ bg: hoverBackground }}
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
