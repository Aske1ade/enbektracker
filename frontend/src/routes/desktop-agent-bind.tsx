import {
  Box,
  Button,
  Center,
  Heading,
  Spinner,
  Text,
  VStack,
} from "@chakra-ui/react"
import { createFileRoute } from "@tanstack/react-router"
import { useEffect, useMemo, useState } from "react"

export const Route = createFileRoute("/desktop-agent-bind")({
  component: DesktopAgentBindPage,
})

type BindStatus = "running" | "success" | "error"

function DesktopAgentBindPage() {
  const [status, setStatus] = useState<BindStatus>("running")
  const [message, setMessage] = useState("Запускаем привязку аккаунта...")
  const [loginUrl, setLoginUrl] = useState<string | null>(null)

  const params = useMemo(() => new URLSearchParams(window.location.search), [])

  useEffect(() => {
    let cancelled = false

    const run = async () => {
      const state = params.get("state")
      const port = params.get("port")
      if (!state || !port) {
        setStatus("error")
        setMessage("Некорректная ссылка привязки. Запустите привязку из агента заново.")
        return
      }

      const token = localStorage.getItem("access_token")
      if (!token) {
        const redirect = `${window.location.pathname}${window.location.search}`
        setStatus("error")
        setLoginUrl(`/login?redirect=${encodeURIComponent(redirect)}`)
        setMessage(
          `В браузере не найден access_token для ${window.location.origin}. Войдите в систему на этом же адресе и повторите привязку.`,
        )
        return
      }

      setMessage("Отправляем подтверждение в агент...")

      try {
        const response = await fetch(
          `http://127.0.0.1:${port}/callback?state=${encodeURIComponent(state)}`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ token }),
          },
        )

        if (!response.ok) {
          const errorText = await response.text()
          throw new Error(
            errorText || `HTTP ${response.status} при привязке аккаунта`,
          )
        }

        if (cancelled) return
        setStatus("success")
        setMessage(
          "Аккаунт успешно привязан. Можно закрыть эту вкладку и работать через трей.",
        )
      } catch (error) {
        if (cancelled) return
        setStatus("error")
        setMessage(
          `Не удалось завершить привязку: ${String(error)}. Проверьте, что агент запущен.`,
        )
      }
    }

    void run()

    return () => {
      cancelled = true
    }
  }, [params])

  return (
    <Center minH="100vh" bg="#F3F6FB" px={4}>
      <Box
        w="100%"
        maxW="560px"
        bg="white"
        borderWidth="1px"
        borderColor="ui.border"
        borderRadius="10px"
        p={6}
        boxShadow="sm"
      >
        <VStack align="start" spacing={4}>
          <Heading size="md">Привязка Enbek Tracker Агента</Heading>

          {status === "running" ? (
            <VStack align="start" spacing={2}>
              <Spinner size="sm" />
              <Text>{message}</Text>
            </VStack>
          ) : null}

          {status === "success" ? (
            <Text color="green.700" fontWeight="600">
              {message}
            </Text>
          ) : null}

          {status === "error" ? (
            <VStack align="start" spacing={2}>
              <Text color="red.700" fontWeight="600">
                {message}
              </Text>
              {loginUrl ? (
                <Button
                  variant="primary"
                  onClick={() => window.location.assign(loginUrl)}
                >
                  Перейти ко входу
                </Button>
              ) : null}
            </VStack>
          ) : null}

          <Button
            variant="primary"
            onClick={() => window.location.assign("/tasks")}
          >
            Открыть Enbek Tracker
          </Button>
        </VStack>
      </Box>
    </Center>
  )
}
