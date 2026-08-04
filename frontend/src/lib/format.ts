/**
 * The backend serialises `datetime.utcnow()`, producing an ISO string with no
 * timezone designator (`2026-08-04T07:39:20`). `new Date()` would read that as
 * local time and shift every timestamp by the UTC offset, so a `Z` is appended
 * unless the value already carries one.
 */
function parseUtc(value: string): Date | null {
  const normalized = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value) ? value : `${value}Z`
  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? null : date
}

const DATE_TIME_FORMAT: Intl.DateTimeFormatOptions = {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
}

/** Formats an ISO timestamp for display, tolerating null and unparsable input. */
export function formatDateTime(value?: string | null): string | null {
  if (!value) return null
  const date = parseUtc(value)
  return date ? date.toLocaleString('zh-CN', DATE_TIME_FORMAT) : null
}

const MINUTE_MS = 60_000
const HOUR_MS = 60 * MINUTE_MS
const DAY_MS = 24 * HOUR_MS

/**
 * Relative time is the primary reading for monitoring data: "3 分钟前" answers
 * "is this fresh?" faster than an absolute clock time. Callers pair it with
 * `formatDateTime` in a `title` attribute for the exact value.
 */
export function formatRelativeTime(value?: string | null, now = Date.now()): string | null {
  if (!value) return null
  const date = parseUtc(value)
  if (!date) return null

  const elapsed = now - date.getTime()
  if (elapsed < MINUTE_MS) return '刚刚'
  if (elapsed < HOUR_MS) return `${Math.floor(elapsed / MINUTE_MS)} 分钟前`
  if (elapsed < DAY_MS) return `${Math.floor(elapsed / HOUR_MS)} 小时前`
  if (elapsed < 30 * DAY_MS) return `${Math.floor(elapsed / DAY_MS)} 天前`
  return formatDateTime(value)
}

/**
 * True when a check is overdue by more than two intervals, meaning the displayed
 * status may no longer reflect reality.
 */
export function isStale(
  lastCheckedAt: string | null | undefined,
  checkIntervalSeconds: number,
  now = Date.now(),
): boolean {
  if (!lastCheckedAt) return false
  const date = parseUtc(lastCheckedAt)
  if (!date) return false
  return now - date.getTime() > checkIntervalSeconds * 2000
}

/** Renders a check interval as a duration, or the disabled placeholder. */
export function formatInterval(enabled: boolean, seconds: number): string {
  if (!enabled) return '关闭'
  if (seconds % 3600 === 0) return `${seconds / 3600} 小时`
  if (seconds % 60 === 0) return `${seconds / 60} 分钟`
  return `${seconds} 秒`
}

export function formatResponseMs(value?: number | null): string {
  return value == null ? '—' : `${value}ms`
}
