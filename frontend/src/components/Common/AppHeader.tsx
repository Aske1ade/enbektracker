import {
  Avatar,
  Badge,
  Box,
  Button,
  Flex,
  HStack,
  IconButton,
  Menu,
  MenuButton,
  MenuItem,
  MenuList,
  Popover,
  PopoverBody,
  PopoverContent,
  PopoverHeader,
  PopoverTrigger,
  Text,
  VStack,
  useColorModeValue,
} from "@chakra-ui/react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { useEffect, useMemo, useState } from "react"
import { FiBell, FiDownload, FiLogOut, FiSettings, FiUser } from "react-icons/fi"

import type { UserPublic } from "../../client"
import { resolveApiBase } from "../../config/api"
import useAuth from "../../hooks/useAuth"
import { readUserAvatar } from "../../hooks/useUserAvatar"
import { readNotificationPreferences } from "../../hooks/useUserPreferences"
import { trackerApi } from "../../services/trackerApi"

const AppHeader = () => {
  const queryClient = useQueryClient()
  const { logout } = useAuth()
  const [avatarSrc, setAvatarSrc] = useState<string | null>(null)
  const desktopAgentUrl = `${resolveApiBase()}/utils/desktop-agent/download`

  const currentUser = queryClient.getQueryData<
    UserPublic & { system_role?: string }
  >(["currentUser"])

  useEffect(() => {
    setAvatarSrc(readUserAvatar(currentUser?.id))
  }, [currentUser?.id])

  useEffect(() => {
    const handler = () => setAvatarSrc(readUserAvatar(currentUser?.id))
    window.addEventListener("tracker-avatar-updated", handler)
    return () => {
      window.removeEventListener("tracker-avatar-updated", handler)
    }
  }, [currentUser?.id])

  const { data: desktopEvents } = useQuery({
    queryKey: ["desktop-events-header"],
    queryFn: () => trackerApi.pollDesktopEvents({ limit: 200 }),
    enabled: Boolean(currentUser?.id),
    refetchInterval: 30_000,
    retry: false,
  })

  const recentEvents = useMemo(() => {
    const prefs = readNotificationPreferences(currentUser?.id)
    if (!prefs.desktop_enabled) return []
    const allowedType = (eventType: string) => {
      if (eventType === "assign") return prefs.assignment_enabled
      if (eventType === "due_soon") return prefs.due_soon_enabled
      if (eventType === "overdue") return prefs.overdue_enabled
      if (eventType === "status_changed") return prefs.status_enabled
      return true
    }
    return [...(desktopEvents?.data ?? [])]
      .filter((event) => allowedType(event.event_type))
      .sort((a, b) => b.id - a.id)
      .slice(0, 8)
  }, [currentUser?.id, desktopEvents?.data])

  const headerBg = useColorModeValue(
    "linear-gradient(180deg, #FFFFFF 0%, #F7FAFF 100%)",
    "linear-gradient(180deg, #020617 0%, #020617 100%)",
  )
  const headerBorderColor = useColorModeValue(
    "ui.border",
    "rgba(148, 163, 184, 0.35)",
  )
  const titleColor = useColorModeValue("ui.darkSlate", "#E5E7EB")

  return (
    <Flex
      as="header"
      h="68px"
      borderBottomWidth="1px"
      borderColor={headerBorderColor}
      bg={headerBg}
      px={{ base: 3, md: 5 }}
      align="center"
      justify="space-between"
      position="sticky"
      top={0}
      zIndex={20}
    >
      <Box minW={{ base: "0", xl: "260px" }} />

      <HStack
        flex={1}
        justify="center"
        spacing={{ base: 2, md: 3 }}
        display={{ base: "none", md: "flex" }}
        minW={0}
      >
        <Box
          as="img"
          src="/Emblem_of_Kazakhstan_latin.svg"
          alt="Эмблема Республики Казахстан"
          w={{ base: "30px", md: "34px" }}
          h={{ base: "30px", md: "34px" }}
          objectFit="contain"
        />
        <Text
          fontSize={{ base: "14px", md: "15px" }}
          fontWeight="700"
          color={titleColor}
          noOfLines={1}
        >
          Министерство труда и социальной защиты населения Республики Казахстан
        </Text>
      </HStack>

      <HStack spacing={3}>
        <Popover placement="bottom-end">
          <PopoverTrigger>
            <Button
              variant="subtle"
              size="sm"
              px={2}
              leftIcon={<FiBell />}
              position="relative"
            >
              Уведомления
              {!!recentEvents.length && (
                <Badge
                  ml={1}
                  colorScheme="red"
                  borderRadius="full"
                  minW="18px"
                  textAlign="center"
                >
                  {recentEvents.length}
                </Badge>
              )}
            </Button>
          </PopoverTrigger>
          <PopoverContent borderColor="ui.border" maxW="420px">
            <PopoverHeader
              fontWeight="700"
              fontSize="sm"
              borderBottomWidth="1px"
              borderColor="ui.border"
            >
              Последние события
            </PopoverHeader>
            <PopoverBody maxH="360px" overflowY="auto" p={0}>
              {!recentEvents.length && (
                <Text px={4} py={3} color="ui.muted" fontSize="sm">
                  Новых событий нет
                </Text>
              )}
              {recentEvents.map((event) => (
                <Box
                  key={event.id}
                  px={4}
                  py={3}
                  borderBottomWidth="1px"
                  borderColor="ui.secondary"
                >
                  <HStack justify="space-between" align="start">
                    <VStack align="start" spacing={0}>
                      <Text fontSize="sm" fontWeight="600">
                        {event.title}
                      </Text>
                      <Text fontSize="xs" color="ui.muted">
                        {event.message}
                      </Text>
                      <Text fontSize="xs" color="ui.dim">
                        {new Date(event.created_at).toLocaleString()}
                      </Text>
                    </VStack>
                    {event.task_id ? (
                      <Button
                        as="a"
                        href={`/tasks?taskId=${event.task_id}`}
                        size="xs"
                        variant="subtle"
                      >
                        Открыть
                      </Button>
                    ) : null}
                  </HStack>
                </Box>
              ))}
            </PopoverBody>
          </PopoverContent>
        </Popover>

        <Menu>
          <MenuButton
            as={IconButton}
            aria-label="Профиль"
            variant="subtle"
            icon={
              <Avatar
                size="sm"
                name={currentUser?.full_name || currentUser?.email}
                src={avatarSrc || undefined}
              />
            }
          />
          <MenuList borderColor="ui.border">
            <MenuItem icon={<FiUser />} as={Link} to="/settings">
              Профиль
            </MenuItem>
            <MenuItem icon={<FiSettings />} as={Link} to="/settings">
              Настройки
            </MenuItem>
            <MenuItem
              icon={<FiDownload />}
              as="a"
              href={desktopAgentUrl}
              target="_blank"
              rel="noreferrer"
            >
              Скачать desktop-агент
            </MenuItem>
            <MenuItem icon={<FiLogOut />} color="ui.danger" onClick={logout}>
              Выйти
            </MenuItem>
          </MenuList>
        </Menu>
      </HStack>
    </Flex>
  )
}

export default AppHeader
