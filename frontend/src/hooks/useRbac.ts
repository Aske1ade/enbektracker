import { useQueryClient } from "@tanstack/react-query"

import type { UserPublic } from "../client"

export const useRbac = () => {
  const queryClient = useQueryClient()
  const currentUser = queryClient.getQueryData<
    UserPublic & { system_role?: string }
  >(["currentUser"])

  const systemRole =
    currentUser?.system_role ??
    (currentUser?.is_superuser ? "admin" : "executor")

  const isLeadership =
    currentUser?.is_superuser ||
    systemRole === "manager" ||
    systemRole === "admin"
  const isController = isLeadership || systemRole === "controller"

  return {
    currentUser,
    systemRole,
    isLeadership,
    isController,
  }
}

export default useRbac
