import type { ReactNode } from 'react'
import type { Status } from '../types'

const STATUS_LABEL: Record<Status, string> = {
  online: '在线',
  offline: '离线',
  unknown: '未知',
}

export function StatusBadge({ status }: { status: Status }) {
  return (
    <span className="ui-badge" data-status={status}>
      <span className="ui-badge-dot" aria-hidden />
      {STATUS_LABEL[status]}
    </span>
  )
}

export function Tag({
  tone,
  children,
}: {
  tone?: 'success' | 'danger'
  children: ReactNode
}) {
  return (
    <span className="ui-tag" data-tone={tone}>
      {children}
    </span>
  )
}
