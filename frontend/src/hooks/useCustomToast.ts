import { useToast } from "@chakra-ui/react"
import axios from "axios"
import { useCallback } from "react"

type ToastStatus = "success" | "error"
type ShowToastFn = (
  title: string,
  description: string,
  status: ToastStatus,
) => void
type EnhancedToast = ShowToastFn & {
  success: (title: string, description: string) => void
  error: (title: string, error: unknown) => void
  getErrorMessage: (error: unknown) => string
}

const useCustomToast = () => {
  const toast = useToast()

  const getErrorMessage = useCallback((error: unknown): string => {
    if (axios.isAxiosError(error)) {
      const data = error.response?.data as
        | { detail?: string; message?: string; code?: string }
        | undefined
      if (data?.detail) return data.detail
      if (data?.message) return data.message
      if (error.message) return error.message
      return "Ошибка запроса к API"
    }
    if (error instanceof Error) return error.message
    return String(error)
  }, [])

  const showToast = useCallback<ShowToastFn>(
    (title: string, description: string, status: "success" | "error") => {
      toast({
        title,
        description,
        status,
        isClosable: true,
        position: "bottom-right",
      })
    },
    [toast],
  )

  const enhanced = showToast as EnhancedToast
  enhanced.success = (title: string, description: string) =>
    showToast(title, description, "success")
  enhanced.error = (title: string, error: unknown) =>
    showToast(title, getErrorMessage(error), "error")
  enhanced.getErrorMessage = getErrorMessage

  return enhanced
}

export default useCustomToast
