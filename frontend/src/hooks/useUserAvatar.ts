const AVATAR_STORAGE_PREFIX = "tracker.user.avatar.v1"

export const getAvatarStorageKey = (userId: number | undefined) =>
  userId ? `${AVATAR_STORAGE_PREFIX}.${userId}` : ""

export const readUserAvatar = (userId: number | undefined): string | null => {
  const key = getAvatarStorageKey(userId)
  if (!key) return null
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

export const writeUserAvatar = (
  userId: number | undefined,
  dataUrl: string,
): void => {
  const key = getAvatarStorageKey(userId)
  if (!key) return
  localStorage.setItem(key, dataUrl)
  window.dispatchEvent(
    new CustomEvent("tracker-avatar-updated", { detail: { userId } }),
  )
}

export const clearUserAvatar = (userId: number | undefined): void => {
  const key = getAvatarStorageKey(userId)
  if (!key) return
  localStorage.removeItem(key)
  window.dispatchEvent(
    new CustomEvent("tracker-avatar-updated", { detail: { userId } }),
  )
}
