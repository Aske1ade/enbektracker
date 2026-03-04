import { Box, Spinner, Text, VStack } from "@chakra-ui/react"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { useEffect } from "react"

export const Route = createFileRoute("/_layout/tasks/$taskId")({
  component: TaskDetailRedirect,
})

function TaskDetailRedirect() {
  const { taskId } = Route.useParams()
  const navigate = useNavigate()

  useEffect(() => {
    navigate({
      to: "/tasks",
      search: { taskId } as never,
      replace: true,
    })
  }, [navigate, taskId])

  return (
    <Box py={8}>
      <VStack spacing={3}>
        <Spinner size="sm" />
        <Text color="ui.muted">Открываем карточку задачи...</Text>
      </VStack>
    </Box>
  )
}
