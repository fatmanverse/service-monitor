import { AlertTriangle, Inbox } from 'lucide-react'
import type { ReactNode } from 'react'

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string
  description: string
  actions?: ReactNode
}) {
  return (
    <header className="page-header">
      <div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {actions && <div className="page-header-actions">{actions}</div>}
    </header>
  )
}

export function Card({ children }: { children: ReactNode }) {
  return <section className="ui-card">{children}</section>
}

export function EmptyState({
  icon,
  title,
  description,
}: {
  icon?: ReactNode
  title: string
  description: string
}) {
  return (
    <div className="empty-state">
      <div className="empty-state-icon">{icon ?? <Inbox size={20} />}</div>
      <strong>{title}</strong>
      <span>{description}</span>
    </div>
  )
}

export function Notice({
  tone = 'warning',
  children,
}: {
  tone?: 'warning' | 'danger'
  children: ReactNode
}) {
  return (
    <div className="ui-notice" data-tone={tone} role="status">
      <AlertTriangle size={17} />
      <div className="ui-notice-body">{children}</div>
    </div>
  )
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="skeleton-list" aria-hidden>
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="skeleton skeleton-row" />
      ))}
    </div>
  )
}
