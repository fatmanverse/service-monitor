import { useEffect, useState } from 'react'
import { RefreshCw, Search } from 'lucide-react'
import type { ReactNode } from 'react'
import { Button } from './Button'
import { formatRelativeTime } from '../lib/format'

export function Toolbar({ children }: { children: ReactNode }) {
  return <div className="toolbar">{children}</div>
}

export function ToolbarSpacer() {
  return <div className="toolbar-spacer" />
}

export function ToolbarCount({ children }: { children: ReactNode }) {
  return <span className="toolbar-count">{children}</span>
}

export function SearchInput({
  value,
  onChange,
  placeholder = '搜索…',
}: {
  value: string
  onChange: (value: string) => void
  placeholder?: string
}) {
  return (
    <div className="search-input">
      <Search size={16} aria-hidden />
      <input
        type="search"
        value={value}
        placeholder={placeholder}
        aria-label={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  )
}

/** Exclusive choice rendered as a compact segmented control. */
export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T
  options: Array<{ value: T; label: string }>
  onChange: (value: T) => void
  label: string
}) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={option.value === value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

const TICK_MS = 30_000

/**
 * Shows how stale the on-screen data is and offers a manual refresh. The label
 * re-renders on a timer so "刚刚" ages into "2 分钟前" without new data arriving.
 */
export function RefreshControl({
  lastUpdatedAt,
  refreshing,
  onRefresh,
}: {
  lastUpdatedAt: number | null
  refreshing: boolean
  onRefresh: () => void
}) {
  const [, setTick] = useState(0)

  useEffect(() => {
    const timer = window.setInterval(() => setTick((value) => value + 1), TICK_MS)
    return () => window.clearInterval(timer)
  }, [])

  const label = lastUpdatedAt
    ? formatRelativeTime(new Date(lastUpdatedAt).toISOString())
    : null

  return (
    <div className="refresh-control">
      {label && (
        <span className="toolbar-count" aria-live="polite">
          {refreshing ? '正在刷新…' : `更新于 ${label}`}
        </span>
      )}
      <Button
        variant="ghost"
        size="icon"
        onClick={onRefresh}
        disabled={refreshing}
        aria-label="刷新数据"
        title="刷新数据"
      >
        <span className="refresh-icon" data-spinning={refreshing || undefined}>
          <RefreshCw size={16} />
        </span>
      </Button>
    </div>
  )
}
