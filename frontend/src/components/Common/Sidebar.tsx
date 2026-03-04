import {
  Avatar,
  Box,
  Drawer,
  DrawerBody,
  DrawerCloseButton,
  DrawerContent,
  DrawerOverlay,
  Flex,
  IconButton,
  Text,
  useDisclosure,
  useColorModeValue,
} from "@chakra-ui/react"
import { useQueryClient } from "@tanstack/react-query"
import { FiLogOut, FiMenu } from "react-icons/fi"

import type { UserPublic } from "../../client"
import useAuth from "../../hooks/useAuth"
import SidebarItems from "./SidebarItems"

const Sidebar = () => {
  const queryClient = useQueryClient()
  const currentUser = queryClient.getQueryData<UserPublic>(["currentUser"])
  const { isOpen, onOpen, onClose } = useDisclosure()
  const { logout } = useAuth()

  const userCardBg = useColorModeValue("white", "rgba(15, 23, 42, 0.95)")
  const logoutHoverBg = useColorModeValue("#FDECEC", "rgba(185, 28, 28, 0.16)")
  const sidebarBg = useColorModeValue("ui.panel", "#020617")

  const content = (
    <Flex direction="column" justify="space-between" h="full">
      <Box>
        <Box
          px={3}
          pb={4}
          borderBottomWidth="1px"
          borderColor="ui.border"
          mb={4}
        >
          <Box
            as="img"
            src="/9d3e6ca7e9bbef28331ec81c8a207f91.png"
            alt="АО «Центр развития трудовых ресурсов»"
            w="190px"
            h="44px"
            objectFit="contain"
          />
          <Text fontWeight="700" fontSize="md" color="ui.main" mt={1}>
            Enbek Tracker
          </Text>
        </Box>
        <SidebarItems onClose={onClose} />
      </Box>

      <Box px={2} pt={4} borderTopWidth="1px" borderColor="ui.border">
        <Box
          px={2}
          py={2}
          borderWidth="1px"
          borderColor="ui.border"
          borderRadius="10px"
          bg={userCardBg}
          mb={2}
        >
          <Flex align="center" gap={2}>
            <Avatar size="sm" name={currentUser?.full_name || currentUser?.email || "Пользователь"} />
            <Box minW={0}>
              <Text fontSize="sm" fontWeight="700" noOfLines={1} color="ui.main">
                {currentUser?.full_name || "Пользователь"}
              </Text>
              <Text fontSize="xs" color="ui.muted" noOfLines={1}>
                {currentUser?.email}
              </Text>
            </Box>
          </Flex>
        </Box>
        <Flex
          as="button"
          onClick={logout}
          align="center"
          gap={2}
          px={2}
          py={2}
          color="ui.danger"
          fontSize="sm"
          borderRadius="6px"
          _hover={{ bg: logoutHoverBg }}
        >
          <FiLogOut />
          Выйти
        </Flex>
      </Box>
    </Flex>
  )

  return (
    <>
      <IconButton
        onClick={onOpen}
        display={{ base: "flex", lg: "none" }}
        aria-label="Открыть меню"
        position="fixed"
        left={3}
        top={3}
        zIndex={40}
        size="sm"
        variant="subtle"
        icon={<FiMenu />}
      />

      <Drawer isOpen={isOpen} placement="left" onClose={onClose}>
        <DrawerOverlay />
        <DrawerContent
          maxW="280px"
          borderRightWidth="1px"
          borderColor="ui.border"
        >
          <DrawerCloseButton />
          <DrawerBody p={3}>{content}</DrawerBody>
        </DrawerContent>
      </Drawer>

      <Box
        w="280px"
        borderRightWidth="1px"
        borderColor="ui.border"
        bg={sidebarBg}
        display={{ base: "none", lg: "block" }}
        position="sticky"
        top={0}
        h="100vh"
      >
        <Box p={3} h="full">
          {content}
        </Box>
      </Box>
    </>
  )
}

export default Sidebar
