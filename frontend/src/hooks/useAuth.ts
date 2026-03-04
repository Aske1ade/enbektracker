import { useMutation, useQuery } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { useState } from "react"

import axios, { AxiosError } from "axios"
import {
  type Body_login_login_access_token as AccessToken,
  ApiError,
  LoginService,
  type Token,
} from "../client"
import { trackerApi } from "../services/trackerApi"
import type { TrackerUser } from "../types/tracker"
import { resolveApiOrigin } from "../config/api"

const isLoggedIn = () => {
  return localStorage.getItem("access_token") !== null
}

const useAuth = () => {
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()
  const { data: user, isLoading } = useQuery<TrackerUser | null, Error>({
    queryKey: ["currentUser"],
    queryFn: () => trackerApi.getCurrentUser(),
    enabled: isLoggedIn(),
  })

  const login = async (data: AccessToken) => {
    const formData = new URLSearchParams()
    formData.set("username", data.username)
    formData.set("password", data.password)
    if (data.grant_type) formData.set("grant_type", data.grant_type)
    if (data.scope) formData.set("scope", data.scope)
    if (data.client_id) formData.set("client_id", data.client_id)
    if (data.client_secret) formData.set("client_secret", data.client_secret)

    try {
      const response = await axios.post<Token>(
        `${resolveApiOrigin()}/api/v1/auth/access-token`,
        formData,
        {
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
          },
        },
      )
      localStorage.setItem("access_token", response.data.access_token)
      return
    } catch (err) {
      // Backward compatibility for older backend route.
      if (!(err instanceof AxiosError) || err.response?.status !== 404) {
        throw err
      }
    }

    const fallbackResponse = await LoginService.loginAccessToken({
      formData: data,
    })
    localStorage.setItem("access_token", fallbackResponse.access_token)
  }

  const loginMutation = useMutation({
    mutationFn: login,
    onSuccess: () => {
      const redirectTarget = new URLSearchParams(window.location.search).get(
        "redirect",
      )
      if (redirectTarget && redirectTarget.startsWith("/")) {
        window.location.assign(redirectTarget)
        return
      }
      navigate({ to: "/" })
    },
    onError: (err: unknown) => {
      let errDetail: string | undefined

      if (err instanceof AxiosError) {
        errDetail = (err.response?.data as any)?.detail || err.message
      } else if (err instanceof ApiError) {
        errDetail = (err.body as any)?.detail
      }

      if (Array.isArray(errDetail)) {
        errDetail = "Something went wrong"
      }

      setError(errDetail ?? "Login failed")
    },
  })

  const logout = () => {
    localStorage.removeItem("access_token")
    navigate({ to: "/login" })
  }

  return {
    loginMutation,
    logout,
    user,
    isLoading,
    error,
    resetError: () => setError(null),
  }
}

export { isLoggedIn }
export default useAuth
