const PROJECT_ACCENT_STORAGE_KEY = "tracker.project.accent-colors.v1"

export const DEFAULT_PROJECT_ICON_PATH = "/assets/project-icons/default-project.svg"

const FALLBACK_ACCENTS = [
  "#1D4ED8",
  "#0F766E",
  "#7C3AED",
  "#B45309",
  "#BE123C",
  "#0369A1",
]

export function resolveProjectIconPath(icon?: string | null): string {
  const raw = (icon || "").trim()
  if (!raw) return DEFAULT_PROJECT_ICON_PATH

  const imageLike =
    raw.startsWith("http://") ||
    raw.startsWith("https://") ||
    raw.startsWith("/") ||
    raw.startsWith("./") ||
    raw.startsWith("../")

  if (!imageLike) return DEFAULT_PROJECT_ICON_PATH
  if (!/\.(svg|png|jpg|jpeg|webp|gif|avif)(\?.*)?$/i.test(raw)) {
    return DEFAULT_PROJECT_ICON_PATH
  }
  return raw
}

export function fallbackAccentBySeed(seed: string): string {
  let hash = 0
  for (const ch of seed) {
    hash = (hash << 5) - hash + ch.charCodeAt(0)
    hash |= 0
  }
  const index = Math.abs(hash) % FALLBACK_ACCENTS.length
  return FALLBACK_ACCENTS[index]
}

function readAccentMap(): Record<string, string> {
  if (typeof window === "undefined") return {}
  try {
    const raw = localStorage.getItem(PROJECT_ACCENT_STORAGE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== "object") return {}
    return parsed as Record<string, string>
  } catch {
    return {}
  }
}

export function readProjectAccent(projectId: number): string | null {
  const value = readAccentMap()[String(projectId)]
  if (!value || typeof value !== "string") return null
  if (!/^#[0-9A-Fa-f]{6}$/.test(value)) return null
  return value
}

export function writeProjectAccent(projectId: number, color: string): void {
  if (typeof window === "undefined") return
  if (!/^#[0-9A-Fa-f]{6}$/.test(color)) return
  const map = readAccentMap()
  map[String(projectId)] = color
  localStorage.setItem(PROJECT_ACCENT_STORAGE_KEY, JSON.stringify(map))
}
