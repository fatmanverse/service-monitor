import { useEffect, useState } from 'react'
import {
  Activity,
  ArrowLeft,
  CheckCircle2,
  Clock3,
  Gauge,
  History,
  Pause,
  Play,
  RefreshCw,
  Server,
  Trash2,
  XCircle,
} from 'lucide-react'
import { api, errorMessage, isAbortError } from '../api'
import { attachProbeNames, canOfferRestart } from '../features/services/serviceActions'
import { useEntityAction } from '../hooks/useEntityAction'
import { formatDateTime } from '../lib/format'
import type { ProbeLog, ProbeResult, Service } from '../types'
import { StatusBadge, Tag } from '../ui/Badge'
import { Button } from '../ui/Button'
import { ConfirmDialog } from '../ui/ConfirmDialog'
import { EmptyState, ErrorState, TableSkeleton } from '../ui/Display'

export function ServiceDetailPage({
  serviceId,
  isAdmin,
  onBack,
}: {
  serviceId: number
  isAdmin: boolean
  onBack: () => void
}) {
  const [service, setService] = useState<Service | null>(null)
  const [logs, setLogs] = useState<ProbeLog[]>([])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [lastResult, setLastResult] = useState<ProbeResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [toggling, setToggling] = useState(false)
  const [error, setError] = useState('')
  const [restartPrompt, setRestartPrompt] = useState(false)
  const [deletePrompt, setDeletePrompt] = useState(false)
  const { run: runAction, phaseOf } = useEntityAction()
  const phase = phaseOf(serviceId)

  async function load(signal?: AbortSignal) {
    setLoading(true)
    setError('')
    try {
      const [serviceData, logPage] = await Promise.all([
        api.service(serviceId, { signal }),
        api.serviceLogs(serviceId, null, { signal }),
      ])
      setService(serviceData)
      setLogs(logPage.items)
      setNextCursor(logPage.next_cursor ?? null)
    } catch (requestError) {
      if (!isAbortError(requestError)) setError(errorMessage(requestError))
    } finally {
      if (!signal?.aborted) setLoading(false)
    }
  }

  async function refreshAfterAction() {
    const [serviceData, logPage] = await Promise.all([
      api.service(serviceId),
      api.serviceLogs(serviceId),
    ])
    setService(serviceData)
    setLogs(logPage.items)
    setNextCursor(logPage.next_cursor ?? null)
  }

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    return () => controller.abort()
  }, [serviceId])

  async function probe() {
    if (!service) return
    setError('')
    try {
      const result = await runAction(service.id, () => api.probeService(service.id))
      if (!result) return
      const normalized = attachProbeNames(result, service)
      setLastResult(normalized)
      setRestartPrompt(canOfferRestart(normalized, service, isAdmin))
      await refreshAfterAction()
    } catch (requestError) {
      setError(errorMessage(requestError))
    }
  }

  async function restart() {
    if (!service) return
    setError('')
    try {
      const result = await runAction(service.id, () => api.restartService(service.id))
      if (result) setLastResult(attachProbeNames(result, service))
      setRestartPrompt(false)
      await refreshAfterAction()
    } catch (requestError) {
      setError(errorMessage(requestError))
    }
  }

  async function toggleMonitoring() {
    if (!service) return
    setToggling(true)
    setError('')
    try {
      const updated = await api.updateService(service.id, { enabled: !service.enabled })
      setService(updated)
    } catch (requestError) {
      setError(errorMessage(requestError))
    } finally {
      setToggling(false)
    }
  }

  async function loadMore() {
    if (!nextCursor) return
    setLoadingMore(true)
    try {
      const page = await api.serviceLogs(serviceId, nextCursor)
      setLogs((current) => [...current, ...page.items])
      setNextCursor(page.next_cursor ?? null)
    } catch (requestError) {
      setError(errorMessage(requestError))
    } finally {
      setLoadingMore(false)
    }
  }

  async function remove() {
    try {
      await api.deleteService(serviceId)
      onBack()
    } catch (requestError) {
      setDeletePrompt(false)
      setError(errorMessage(requestError))
    }
  }

  if (loading) {
    return (
      <div className="service-detail-loading">
        <TableSkeleton rows={6} />
      </div>
    )
  }
  if (error && !service) return <ErrorState message={error} onRetry={() => void load()} />
  if (!service) {
    return (
      <EmptyState
        icon={<Server size={20} />}
        title="服务不可用"
        description="该服务不存在，或当前账号没有查看权限。"
        action={<Button onClick={onBack}>返回服务列表</Button>}
      />
    )
  }

  return (
    <div className="service-detail">
      <header className="detail-heading">
        <Button size="icon" variant="ghost" onClick={onBack} aria-label="返回服务列表" title="返回">
          <ArrowLeft size={18} />
        </Button>
        <div className="detail-heading-copy">
          <span>{service.resource_group_name} / {service.host_name}</span>
          <div><h1>{service.name}</h1><StatusBadge status={service.status} /></div>
        </div>
        <div className="detail-actions">
          <Button
            variant="primary"
            icon={<Activity size={16} />}
            loading={phase !== 'idle'}
            onClick={() => void probe()}
          >
            {phase === 'queued' ? '等待 Agent' : '立即探活'}
          </Button>
          {isAdmin && (
            <Button
              icon={service.enabled ? <Pause size={16} /> : <Play size={16} />}
              loading={toggling}
              onClick={() => void toggleMonitoring()}
            >
              {service.enabled ? '停止监控' : '启用监控'}
            </Button>
          )}
          {isAdmin && (
            <Button
              size="icon"
              variant="danger"
              onClick={() => setDeletePrompt(true)}
              aria-label="删除服务"
              title="删除服务"
            >
              <Trash2 size={16} />
            </Button>
          )}
        </div>
      </header>

      {error && <div className="detail-error" role="alert">{error}</div>}

      <section className="detail-summary" aria-label="服务状态摘要">
        <div><Server size={18} /><span>所属节点</span><strong>{service.host_name}</strong></div>
        <div><Clock3 size={18} /><span>定时探活</span><strong>{service.enabled ? `${service.check_interval} 秒` : '已停止'}</strong></div>
        <div><Gauge size={18} /><span>最近响应</span><strong>{service.last_response_ms == null ? '暂无' : `${service.last_response_ms} ms`}</strong></div>
        <div><History size={18} /><span>最近检查</span><strong>{service.last_checked_at ? formatDateTime(service.last_checked_at) : '尚未探活'}</strong></div>
      </section>

      {lastResult && (
        <section className="probe-result" data-success={lastResult.success === true}>
          <header>
            {lastResult.success ? <CheckCircle2 size={20} /> : <XCircle size={20} />}
            <div>
              <span>本次探活结果</span>
              <strong>{lastResult.success ? '服务在线' : '服务离线'}</strong>
            </div>
            <span>{lastResult.response_ms == null ? '无耗时数据' : `${lastResult.response_ms} ms`}</span>
          </header>
          <p>{lastResult.message}</p>
          {lastResult.probes.length > 0 && (
            <div className="probe-result-items">
              {lastResult.probes.map((probe) => (
                <div key={probe.key}>
                  <Tag tone={probe.success ? 'success' : 'danger'}>{probe.name}</Tag>
                  <span>{probe.message}</span>
                  <small>{probe.response_ms == null ? '—' : `${probe.response_ms} ms`}</small>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      <div className="detail-columns">
        <section className="detail-panel">
          <header><div><span>探活配置</span><h2>检查项</h2></div><strong>{service.probes.length}</strong></header>
          <div className="probe-list">
            {service.probes.map((probe) => (
              <article key={probe.key}>
                <div className="probe-state" data-success={probe.last_success === true} data-failed={probe.last_success === false} />
                <div>
                  <strong>{probe.name}</strong>
                  <span>{probe.probe_type.toUpperCase()} · {probe.enabled ? '已启用' : '已停用'}</span>
                  <p>{probe.last_error || (probe.last_checked_at ? `最近检查 ${formatDateTime(probe.last_checked_at)}` : '等待首次检查')}</p>
                </div>
                <small>{probe.last_response_ms == null ? '—' : `${probe.last_response_ms} ms`}</small>
              </article>
            ))}
          </div>
        </section>

        <section className="detail-panel history-panel">
          <header><div><span>最近 30 天</span><h2>探活历史</h2></div><History size={19} /></header>
          {logs.length === 0 ? (
            <EmptyState title="暂无历史记录" description="执行一次探活后，结果会显示在这里。" />
          ) : (
            <ol className="history-list">
              {logs.map((log) => (
                <li key={log.id} data-success={log.success}>
                  <span className="history-dot" />
                  <div><strong>{log.success ? '在线' : '离线'}</strong><p>{log.message}</p></div>
                  <div><span>{formatDateTime(log.checked_at)}</span><small>{log.response_ms == null ? '—' : `${log.response_ms} ms`}</small></div>
                </li>
              ))}
            </ol>
          )}
          {nextCursor && (
            <Button
              variant="ghost"
              icon={<RefreshCw size={15} />}
              loading={loadingMore}
              onClick={() => void loadMore()}
            >
              加载更早记录
            </Button>
          )}
        </section>
      </div>

      {restartPrompt && (
        <ConfirmDialog
          title="服务当前离线"
          message={`本次探活确认“${service.name}”离线。是否执行已配置的启动命令并立即复检？`}
          confirmLabel="拉起服务"
          tone="primary"
          busy={phase !== 'idle'}
          onConfirm={() => void restart()}
          onCancel={() => setRestartPrompt(false)}
        />
      )}
      {deletePrompt && (
        <ConfirmDialog
          title="删除服务"
          message={`确认删除“${service.name}”及其探活历史？此操作不可恢复。`}
          busy={false}
          onConfirm={() => void remove()}
          onCancel={() => setDeletePrompt(false)}
        />
      )}
    </div>
  )
}
