export type NotificationPreferences = {
  desktop_enabled: boolean
  sound_enabled: boolean
  assignment_enabled: boolean
  due_soon_enabled: boolean
  overdue_enabled: boolean
  status_enabled: boolean
  quiet_hours_enabled: boolean
  quiet_hours_from: string
  quiet_hours_to: string
}

export type AdvancedProfilePreferences = {
  position: string
  phone: string
  telegram: string
  locale: string
  timezone: string
  signature: string
}

const DEFAULT_NOTIFICATION_PREFERENCES: NotificationPreferences = {
  desktop_enabled: true,
  sound_enabled: true,
  assignment_enabled: true,
  due_soon_enabled: true,
  overdue_enabled: true,
  status_enabled: true,
  quiet_hours_enabled: false,
  quiet_hours_from: "22:00",
  quiet_hours_to: "08:00",
}

const DEFAULT_ADVANCED_PROFILE: AdvancedProfilePreferences = {
  position: "",
  phone: "",
  telegram: "",
  locale: "ru-RU",
  timezone: "Asia/Almaty",
  signature: "",
}

function parseStored<T>(raw: string | null, fallback: T): T {
  if (!raw) return fallback
  try {
    return { ...fallback, ...JSON.parse(raw) }
  } catch {
    return fallback
  }
}

function key(prefix: string, userId?: number | null): string {
  return `${prefix}:${userId ?? "anonymous"}`
}

export function readNotificationPreferences(
  userId?: number | null,
): NotificationPreferences {
  return parseStored(
    localStorage.getItem(key("tracker.notification-preferences", userId)),
    DEFAULT_NOTIFICATION_PREFERENCES,
  )
}

export function writeNotificationPreferences(
  userId: number | null | undefined,
  value: NotificationPreferences,
): void {
  localStorage.setItem(
    key("tracker.notification-preferences", userId),
    JSON.stringify(value),
  )
}

export function readAdvancedProfilePreferences(
  userId?: number | null,
): AdvancedProfilePreferences {
  return parseStored(
    localStorage.getItem(key("tracker.advanced-profile", userId)),
    DEFAULT_ADVANCED_PROFILE,
  )
}

export function writeAdvancedProfilePreferences(
  userId: number | null | undefined,
  value: AdvancedProfilePreferences,
): void {
  localStorage.setItem(
    key("tracker.advanced-profile", userId),
    JSON.stringify(value),
  )
}
