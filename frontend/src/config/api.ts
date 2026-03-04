const stripTrailingSlash = (value: string) => value.replace(/\/+$/, "")

export const resolveApiOrigin = (): string => {
  const envOrigin = import.meta.env.VITE_API_URL?.trim()
  if (envOrigin) {
    return stripTrailingSlash(envOrigin)
  }

  if (typeof window === "undefined") {
    return "http://localhost:8888"
  }

  const { protocol, hostname, port } = window.location
  if (port === "5173" || port === "4173") {
    return `${protocol}//${hostname}:8888`
  }

  return `${protocol}//${hostname}${port ? `:${port}` : ""}`
}

export const resolveApiBase = (): string => `${resolveApiOrigin()}/api/v1`
