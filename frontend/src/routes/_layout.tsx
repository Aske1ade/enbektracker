import {
  Box,
  Button,
  Flex,
  FormControl,
  FormLabel,
  Heading,
  Input,
  Spinner,
  Text,
  useColorModeValue,
} from "@chakra-ui/react"
import { Outlet, createFileRoute, redirect } from "@tanstack/react-router"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

import { UsersService } from "../client"
import AppHeader from "../components/Common/AppHeader"
import Sidebar from "../components/Common/Sidebar"
import useCustomToast from "../hooks/useCustomToast"
import useAuth, { isLoggedIn } from "../hooks/useAuth"

export const Route = createFileRoute("/_layout")({
  component: Layout,
  beforeLoad: async () => {
    if (!isLoggedIn()) {
      throw redirect({
        to: "/login",
      })
    }
  },
})

function Layout() {
  const { isLoading, user, logout } = useAuth()
  const showToast = useCustomToast()
  const queryClient = useQueryClient()
  const pageBg = useColorModeValue("transparent", "transparent")
  const gateBg = useColorModeValue("white", "#162235")
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")

  const forcePasswordMutation = useMutation({
    mutationFn: async () => {
      if (!currentPassword || !newPassword) {
        throw new Error("Заполните текущий и новый пароль")
      }
      if (newPassword !== confirmPassword) {
        throw new Error("Подтверждение пароля не совпадает")
      }
      await UsersService.updatePasswordMe({
        requestBody: {
          current_password: currentPassword,
          new_password: newPassword,
        },
      })
    },
    onSuccess: async () => {
      setCurrentPassword("")
      setNewPassword("")
      setConfirmPassword("")
      await queryClient.invalidateQueries({ queryKey: ["currentUser"] })
      showToast.success("Успешно", "Пароль обновлён")
    },
    onError: (error) =>
      showToast.error("Не удалось обновить пароль", error),
  })

  const mustChangePassword = Boolean((user as { must_change_password?: boolean } | null)?.must_change_password)

  return (
    <Flex w="100%" minH="100vh" position="relative" bg={pageBg}>
      <Sidebar />
      <Flex direction="column" flex={1} minW={0}>
        <AppHeader />
        <Box flex={1} minW={0}>
          {isLoading ? (
            <Flex justify="center" align="center" h="full" w="full">
              <Spinner size="xl" color="ui.main" />
            </Flex>
          ) : mustChangePassword ? (
            <Flex align="center" justify="center" px={4} py={8}>
              <Box
                w="full"
                maxW="520px"
                borderWidth="1px"
                borderColor="ui.border"
                borderRadius="md"
                bg={gateBg}
                p={6}
              >
                <Heading size="md" mb={2}>
                  Требуется смена пароля
                </Heading>
                <Text color="ui.muted" fontSize="sm" mb={4}>
                  Администратор включил обязательную смену пароля для вашего аккаунта.
                </Text>
                <FormControl mb={3} isRequired>
                  <FormLabel>Текущий пароль</FormLabel>
                  <Input
                    type="password"
                    value={currentPassword}
                    onChange={(event) => setCurrentPassword(event.target.value)}
                  />
                </FormControl>
                <FormControl mb={3} isRequired>
                  <FormLabel>Новый пароль</FormLabel>
                  <Input
                    type="password"
                    value={newPassword}
                    onChange={(event) => setNewPassword(event.target.value)}
                  />
                </FormControl>
                <FormControl mb={5} isRequired>
                  <FormLabel>Подтвердите новый пароль</FormLabel>
                  <Input
                    type="password"
                    value={confirmPassword}
                    onChange={(event) => setConfirmPassword(event.target.value)}
                  />
                </FormControl>
                <Flex justify="space-between" gap={3}>
                  <Button variant="ghost" onClick={logout}>
                    Выйти
                  </Button>
                  <Button
                    onClick={() => forcePasswordMutation.mutate()}
                    isLoading={forcePasswordMutation.isPending}
                  >
                    Сменить пароль
                  </Button>
                </Flex>
              </Box>
            </Flex>
          ) : (
            <Outlet />
          )}
        </Box>
      </Flex>
    </Flex>
  )
}
