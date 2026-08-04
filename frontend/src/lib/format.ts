/** Formats an ISO timestamp for display, tolerating null and unparsable input. */
export function formatDateTime(value?: string | null): string | null {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Renders a check interval as a duration, or the disabled placeholder. */
export function formatInterval(enabled: boolean, seconds: number): string {
  return enabled ? `${seconds}s` : '关闭'
}

export function formatResponseMs(value?: number | null): string {
  return value == null ? '—' : `${value}ms`
}
