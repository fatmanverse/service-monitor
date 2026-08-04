import { AlertTriangle, Inbox, RefreshCw } from 'lucide-react'
import type { ReactNode } from 'react'
import { Button } from './Button'

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
  action,
}: {
  icon?: ReactNode
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <div className="empty-state">
      <div className="empty-state-icon">{icon ?? <Inbox size={20} />}</div>
      <strong>{title}</strong>
      <span>{description}</span>
      {action}
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

/**
 * Persistent failure state for a load that produced no data. Transient action
 * failures use a toast instead; this one stays until the user retries.
 */
export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="empty-state" role="alert">
      <div className="empty-state-icon" data-tone="danger">
        <AlertTriangle size={20} />
      </div>
      <strong>数据加载失败</strong>
      <span>{message}</span>
      <Button variant="secondary" icon={<RefreshCw size={15} />} onClick={onRetry}>
        重试
      </Button>
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

export function CardSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="card-grid" aria-hidden>
      {Array.from({ length: count }, (_, index) => (
        <div key={index} className="skeleton skeleton-card" />
      ))}
    </div>
  )
}

export function StatGrid({ children }: { children: ReactNode }) {
  return <div className="stat-grid">{children}</div>
}

export function StatCard({
  label,
  value,
  tone,
  icon,
}: {
  label: string
  value: number | string
  tone?: 'success' | 'danger' | 'warning'
  icon?: ReactNode
}) {
  return (
    <div className="stat-card" data-tone={tone}>
      <div className="stat-card-head">
        {icon}
        {label}
      </div>
      <strong>{value}</strong>
    </div>
  )
}
