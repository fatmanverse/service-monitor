import { useMemo, useState } from 'react'
import {
  CheckCircle2,
  Copy,
  Cpu,
  KeyRound,
  Link2,
  RotateCw,
  ShieldX,
  XCircle,
} from 'lucide-react'
import { api, errorMessage } from '../api'
import { useAsyncResource } from '../hooks/useAsyncResource'
import { formatDateTime, formatRelativeTime } from '../lib/format'
import type { Agent, Host } from '../types'
import { StatusBadge, Tag } from '../ui/Badge'
import { Button } from '../ui/Button'
import { ConfirmDialog } from '../ui/ConfirmDialog'
import {
  Card,
  EmptyState,
  ErrorState,
  PageHeader,
  StatCard,
  StatGrid,
  TableSkeleton,
} from '../ui/Display'
import { CheckboxField, SelectField, TextField } from '../ui/Field'
import { Modal } from '../ui/Modal'
import { RefreshControl, Segmented, Toolbar, ToolbarCount, ToolbarSpacer } from '../ui/Toolbar'
import { useToast } from '../ui/Toast'

type Filter = 'all' | 'pending' | 'approved' | 'inactive'
type ApprovalMode = 'new' | 'bind'
type ConfirmAction = { kind: 'reject' | 'revoke' | 'rotate'; agent: Agent }

const FILTERS: Array<{ value: Filter; label: string }> = [
  { value: 'all', label: '全部' },
  { value: 'pending', label: '待审批' },
  { value: 'approved', label: '已接入' },
  { value: 'inactive', label: '已停用' },
]

function stateLabel(agent: Agent) {
  return {
    pending: '待审批',
    approved: '已批准',
    rejected: '已拒绝',
    revoked: '已撤销',
  }[agent.status]
}

function stateTone(agent: Agent): 'success' | 'danger' | undefined {
  if (agent.status === 'approved') return 'success'
  if (agent.status === 'rejected' || agent.status === 'revoked') return 'danger'
  return undefined
}

export function AgentsPage() {
  const toast = useToast()
  const agents = useAsyncResource((signal) => api.agents({ signal }), { pollIntervalMs: 10_000 })
  const hosts = useAsyncResource((signal) => api.hosts({ signal }))
  const [filter, setFilter] = useState<Filter>('all')
  const [approving, setApproving] = useState<Agent | null>(null)
  const [approvalMode, setApprovalMode] = useState<ApprovalMode>('new')
  const [hostName, setHostName] = useState('')
  const [hostId, setHostId] = useState('')
  const [acknowledged, setAcknowledged] = useState(false)
  const [confirmAction, setConfirmAction] = useState<ConfirmAction | null>(null)
  const [secret, setSecret] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [formError, setFormError] = useState('')

  const items = agents.data ?? []
  const bindableHosts = (hosts.data ?? []).filter((host) => host.execution_mode === 'ssh')
  const filtered = useMemo(
    () =>
      items.filter((agent) => {
        if (filter === 'all') return true
        if (filter === 'inactive') return agent.status === 'rejected' || agent.status === 'revoked'
        return agent.status === filter
      }),
    [filter, items],
  )

  function openApprove(agent: Agent) {
    setApproving(agent)
    setApprovalMode('new')
    setHostName(agent.hostname)
    setHostId('')
    setAcknowledged(false)
    setFormError('')
  }

  async function submitApproval() {
    if (!approving) return
    if (approvalMode === 'new' && !hostName.trim()) {
      setFormError('请输入新主机名称。')
      return
    }
    if (approvalMode === 'bind' && (!hostId || !acknowledged)) {
      setFormError('请选择主机并确认 SSH 凭据将被永久删除。')
      return
    }
    setBusy(true)
    setFormError('')
    try {
      await api.approveAgent(
        approving.id,
        approvalMode === 'new'
          ? { mode: 'new', host_name: hostName.trim() }
          : { mode: 'bind', host_id: Number(hostId) },
      )
      toast({ tone: 'success', title: 'Agent 已批准', detail: approving.hostname })
      setApproving(null)
      await Promise.all([agents.refresh(), hosts.refresh()])
    } catch (error) {
      setFormError(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  async function runConfirmedAction() {
    if (!confirmAction) return
    setBusy(true)
    try {
      const { agent, kind } = confirmAction
      if (kind === 'reject') await api.rejectAgent(agent.id)
      if (kind === 'revoke') await api.revokeAgent(agent.id)
      if (kind === 'rotate') {
        const result = await api.rotateAgentSecret(agent.id)
        setSecret(result.agent_secret)
      }
      toast({
        tone: kind === 'rotate' ? 'success' : 'info',
        title: kind === 'reject' ? '申请已拒绝' : kind === 'revoke' ? 'Agent 已撤销' : '密钥已轮换',
        detail: agent.hostname,
      })
      setConfirmAction(null)
      await agents.refresh()
    } catch (error) {
      toast({ tone: 'danger', title: '操作失败', detail: errorMessage(error) })
    } finally {
      setBusy(false)
    }
  }

  async function copySecret() {
    if (!secret) return
    await navigator.clipboard.writeText(secret)
    toast({ tone: 'success', title: '密钥已复制' })
  }

  const initialError = agents.error && !agents.data

  return (
    <>
      <PageHeader
        title="Agent 接入"
        description="审批节点注册、绑定主机并管理每个 Agent 的独立认证密钥。"
      />

      <StatGrid>
        <StatCard label="Agent 总数" value={items.length} icon={<Cpu size={16} />} />
        <StatCard
          label="待审批"
          value={items.filter((agent) => agent.status === 'pending').length}
          tone="warning"
          icon={<Link2 size={16} />}
        />
        <StatCard
          label="在线"
          value={items.filter((agent) => agent.status === 'approved' && agent.host?.status === 'online').length}
          tone="success"
          icon={<CheckCircle2 size={16} />}
        />
        <StatCard
          label="离线"
          value={items.filter((agent) => agent.status === 'approved' && agent.host?.status !== 'online').length}
          tone="danger"
          icon={<XCircle size={16} />}
        />
      </StatGrid>

      <Toolbar>
        <Segmented value={filter} options={FILTERS} onChange={setFilter} label="Agent 状态筛选" />
        <ToolbarSpacer />
        <ToolbarCount>{filtered.length} 个 Agent</ToolbarCount>
        <RefreshControl
          lastUpdatedAt={agents.lastUpdatedAt}
          refreshing={agents.refreshing}
          onRefresh={() => void agents.refresh()}
        />
      </Toolbar>

      <Card>
        {agents.initialLoading ? (
          <TableSkeleton rows={5} />
        ) : initialError ? (
          <ErrorState message={agents.error?.message ?? '加载失败'} onRetry={() => void agents.refresh()} />
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={<Cpu size={20} />}
            title="没有匹配的 Agent"
            description="Agent 首次连接 gRPC 服务后会在这里显示待审批申请。"
          />
        ) : (
          <div className="table-scroll">
            <table className="ui-table agent-table">
              <thead>
                <tr>
                  <th>节点</th>
                  <th>环境</th>
                  <th>状态</th>
                  <th>绑定主机</th>
                  <th>最后心跳</th>
                  <th>配置版本</th>
                  <th aria-label="操作" />
                </tr>
              </thead>
              <tbody>
                {filtered.map((agent) => (
                  <tr key={agent.id}>
                    <td>
                      <div className="cell-primary">
                        <span className="cell-icon"><Cpu size={16} /></span>
                        <span className="cell-primary-text">
                          <strong>{agent.hostname}</strong>
                          <span>{agent.runtime_user} · {agent.agent_uuid.slice(0, 12)}…</span>
                        </span>
                      </div>
                    </td>
                    <td>
                      <div className="agent-environment">
                        <span>{agent.os_release}</span>
                        <small>{agent.architecture} · glibc {agent.glibc_version} · v{agent.agent_version}</small>
                      </div>
                    </td>
                    <td><Tag tone={stateTone(agent)}>{stateLabel(agent)}</Tag></td>
                    <td>
                      {agent.host ? (
                        <div className="agent-host-cell">
                          <span>{agent.host.name}</span>
                          <StatusBadge status={agent.host.status} />
                        </div>
                      ) : '—'}
                    </td>
                    <td
                      className="cell-muted"
                      title={formatDateTime(agent.last_seen_at) ?? undefined}
                    >
                      {formatRelativeTime(agent.last_seen_at) ?? '尚未认证'}
                    </td>
                    <td className="u-mono">r{agent.config_revision}</td>
                    <td>
                      <div className="row-actions">
                        {agent.status === 'pending' && (
                          <>
                            <Button size="sm" variant="primary" icon={<Link2 size={15} />} onClick={() => openApprove(agent)}>批准</Button>
                            <Button size="icon" variant="danger" onClick={() => setConfirmAction({ kind: 'reject', agent })} aria-label={`拒绝 ${agent.hostname}`} title="拒绝申请"><ShieldX size={16} /></Button>
                          </>
                        )}
                        {agent.status === 'approved' && (
                          <>
                            <Button size="icon" variant="ghost" onClick={() => setConfirmAction({ kind: 'rotate', agent })} aria-label={`轮换 ${agent.hostname} 密钥`} title="轮换密钥"><RotateCw size={16} /></Button>
                            <Button size="icon" variant="danger" onClick={() => setConfirmAction({ kind: 'revoke', agent })} aria-label={`撤销 ${agent.hostname}`} title="撤销 Agent"><ShieldX size={16} /></Button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {approving && (
        <Modal
          title={`批准 Agent · ${approving.hostname}`}
          description="选择创建新主机，或将 Agent 绑定到已有 SSH 主机。"
          busy={busy}
          onClose={() => setApproving(null)}
          footer={
            <>
              <Button onClick={() => setApproving(null)} disabled={busy}>取消</Button>
              <Button variant="primary" loading={busy} onClick={() => void submitApproval()}>批准接入</Button>
            </>
          }
        >
          <div className="approval-form">
            <Segmented
              value={approvalMode}
              options={[{ value: 'new', label: '新建主机' }, { value: 'bind', label: '绑定已有主机' }]}
              onChange={(value) => {
                setApprovalMode(value)
                setFormError('')
                setAcknowledged(false)
              }}
              label="批准方式"
            />
            {approvalMode === 'new' ? (
              <TextField label="主机名称" value={hostName} onChange={(event) => setHostName(event.target.value)} required />
            ) : (
              <>
                <SelectField label="目标 SSH 主机" value={hostId} onChange={(event) => setHostId(event.target.value)} required>
                  <option value="">请选择</option>
                  {bindableHosts.map((host: Host) => <option key={host.id} value={host.id}>{host.name} · {host.hostname}</option>)}
                </SelectField>
                <CheckboxField
                  label="我确认绑定后将永久删除该主机的 SSH 端口、密码和私钥配置。"
                  checked={acknowledged}
                  onChange={(event) => setAcknowledged(event.target.checked)}
                />
              </>
            )}
            {formError && <div className="form-error" role="alert">{formError}</div>}
          </div>
        </Modal>
      )}

      {confirmAction && (
        <ConfirmDialog
          title={confirmAction.kind === 'rotate' ? '轮换 Agent 密钥' : confirmAction.kind === 'revoke' ? '撤销 Agent' : '拒绝 Agent 申请'}
          message={
            confirmAction.kind === 'rotate'
              ? '旧密钥将立即失效，必须把新密钥安全地更新到节点。'
              : confirmAction.kind === 'revoke'
                ? '撤销后该 Agent 的心跳、配置同步和报告将立即被拒绝。'
                : '拒绝后本次 claim token 将失效，节点需要重新申请。'
          }
          confirmLabel={confirmAction.kind === 'rotate' ? '轮换密钥' : confirmAction.kind === 'revoke' ? '确认撤销' : '确认拒绝'}
          tone="danger"
          busy={busy}
          onCancel={() => setConfirmAction(null)}
          onConfirm={() => void runConfirmedAction()}
        />
      )}

      {secret && (
        <Modal
          title="新 Agent 密钥"
          description="该密钥仅在本次操作中显示。"
          size="sm"
          onClose={() => setSecret(null)}
          footer={<Button variant="primary" onClick={() => setSecret(null)}>我已保存</Button>}
        >
          <div className="secret-panel">
            <KeyRound size={18} />
            <code>{secret}</code>
            <Button size="icon" variant="secondary" onClick={() => void copySecret()} aria-label="复制密钥" title="复制密钥"><Copy size={16} /></Button>
          </div>
        </Modal>
      )}
    </>
  )
}
