import { useEffect, useState } from 'react'
import { Activity, CheckCircle2, Pencil, Plus, Server, Trash2, XCircle } from 'lucide-react'
import { api, errorMessage } from '../api'
import { AlertTargetPicker } from '../components/AlertTargetPicker'
import { formatDateTime } from '../lib/format'
import type { AlertConfig, Host } from '../types'
import { StatusBadge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Card, EmptyState, Notice, PageHeader, StatCard, StatGrid } from '../ui/Display'
import { SelectField, TextField } from '../ui/Field'
import { Modal } from '../ui/Modal'

type HostForm = {
  name: string
  hostname: string
  port: string
  username: string
  auth_type: 'password' | 'key'
  password: string
  private_key_path: string
  check_interval: string
  enabled: boolean
  alert_config_ids: number[]
}

const FORM_ID = 'host-form'

function blankForm(): HostForm {
  return {
    name: '',
    hostname: '',
    port: '22',
    username: '',
    auth_type: 'password',
    password: '',
    private_key_path: '',
    check_interval: '60',
    enabled: true,
    alert_config_ids: [],
  }
}

function hostForm(host: Host): HostForm {
  return {
    name: host.name,
    hostname: host.hostname,
    port: String(host.port ?? ''),
    username: host.username,
    auth_type: host.auth_type === 'key' ? 'key' : 'password',
    password: '',
    private_key_path: host.private_key_path || '',
    check_interval: String(host.check_interval),
    enabled: host.enabled,
    alert_config_ids: host.alert_configs.map((config) => config.id),
  }
}

export function HostsPage() {
  const [hosts, setHosts] = useState<Host[]>([])
  const [alertConfigs, setAlertConfigs] = useState<AlertConfig[]>([])
  const [editing, setEditing] = useState<Host | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [form, setForm] = useState<HostForm>(blankForm())
  const [message, setMessage] = useState('')
  const [busyId, setBusyId] = useState<number | null>(null)

  async function load() {
    const [hostResult, alertResult] = await Promise.allSettled([api.hosts(), api.alerts()])
    if (hostResult.status === 'fulfilled') setHosts(hostResult.value)
    else setMessage(errorMessage(hostResult.reason))
    if (alertResult.status === 'fulfilled') setAlertConfigs(alertResult.value)
  }

  useEffect(() => {
    load().catch((error) => setMessage(errorMessage(error)))
  }, [])

  function openCreate() {
    setEditing(null)
    setForm(blankForm())
    setModalOpen(true)
  }

  function openEdit(host: Host) {
    setEditing(host)
    setForm(hostForm(host))
    setModalOpen(true)
  }

  function toggleAlert(configId: number) {
    setForm((current) => ({
      ...current,
      alert_config_ids: current.alert_config_ids.includes(configId)
        ? current.alert_config_ids.filter((id) => id !== configId)
        : [...current.alert_config_ids, configId],
    }))
  }

  async function save(event: React.FormEvent) {
    event.preventDefault()
    setMessage('')
    const payload = editing?.execution_mode === 'agent'
      ? {
          name: form.name,
          check_interval: Number(form.check_interval),
          enabled: form.enabled,
          alert_config_ids: form.alert_config_ids,
        }
      : {
          ...form,
          port: Number(form.port),
          check_interval: Number(form.check_interval),
          password: form.auth_type === 'password' ? form.password || null : null,
          private_key_path: form.auth_type === 'key' ? form.private_key_path : null,
        }
    try {
      if (editing) await api.updateHost(editing.id, payload)
      else await api.createHost(payload)
      setModalOpen(false)
      await load()
    } catch (error) {
      setMessage(errorMessage(error))
    }
  }

  async function probe(host: Host) {
    setBusyId(host.id)
    setMessage('')
    try {
      const result = await api.probeHost(host.id)
      setMessage(`${host.name}：${result.message}`)
      await load()
    } catch (error) {
      setMessage(errorMessage(error))
    } finally {
      setBusyId(null)
    }
  }

  async function remove(host: Host) {
    if (!confirm(`删除主机“${host.name}”将同时删除其所有服务监测，确认继续？`)) return
    try {
      await api.deleteHost(host.id)
      await load()
    } catch (error) {
      setMessage(errorMessage(error))
    }
  }

  const passwordRequired = !editing || editing.auth_type !== 'password'

  return (
    <>
      <PageHeader
        title="主机管理"
        description="维护 SSH 节点连接、主机级探活与节点状态告警。"
        actions={(
          <Button variant="primary" icon={<Plus size={16} />} onClick={openCreate}>
            新增节点
          </Button>
        )}
      />
      {message && <Notice>{message}</Notice>}
      <StatGrid>
        <StatCard label="节点总数" value={hosts.length} icon={<Server size={16} />} />
        <StatCard
          label="在线"
          value={hosts.filter((host) => host.status === 'online').length}
          tone="success"
          icon={<CheckCircle2 size={16} />}
        />
        <StatCard
          label="离线"
          value={hosts.filter((host) => host.status === 'offline').length}
          tone="danger"
          icon={<XCircle size={16} />}
        />
      </StatGrid>
      <Card>
        {hosts.length === 0 ? (
          <EmptyState
            icon={<Server size={20} />}
            title="尚未添加节点"
            description="新增 SSH 节点或批准 Agent 后即可配置服务监测。"
          />
        ) : (
          <div className="table-scroll">
            <table className="ui-table host-table">
              <thead>
                <tr>
                  <th>节点</th>
                  <th>连接地址</th>
                  <th>执行模式</th>
                  <th>周期</th>
                  <th>告警目标</th>
                  <th>状态</th>
                  <th>最后检查</th>
                  <th aria-label="操作" />
                </tr>
              </thead>
              <tbody>
                {hosts.map((host) => (
                  <tr key={host.id}>
                    <td>
                      <div className="cell-primary">
                        <span className="cell-icon"><Server size={16} /></span>
                        <span className="cell-primary-text">
                          <strong>{host.name}</strong>
                          <span>{host.username}</span>
                        </span>
                      </div>
                    </td>
                    <td className="u-mono">
                      {host.execution_mode === 'agent' ? host.hostname : `${host.hostname}:${host.port}`}
                    </td>
                    <td><span className="mode-badge" data-mode={host.execution_mode}>{host.execution_mode === 'agent' ? 'Agent' : 'SSH'}</span></td>
                    <td>{host.enabled ? `${host.check_interval}s` : '关闭'}</td>
                    <td>{host.alert_configs.length}</td>
                    <td><StatusBadge status={host.status} /></td>
                    <td className="cell-muted">{formatDateTime(host.last_checked_at) ?? '尚未检查'}</td>
                    <td>
                      <div className="row-actions">
                        {host.execution_mode === 'ssh' && (
                          <Button
                            size="sm"
                            variant="ghost"
                            icon={<Activity size={15} />}
                            loading={busyId === host.id}
                            onClick={() => void probe(host)}
                          >
                            探活
                          </Button>
                        )}
                        <Button size="icon" variant="ghost" onClick={() => openEdit(host)} aria-label={`编辑 ${host.name}`} title="编辑节点">
                          <Pencil size={16} />
                        </Button>
                        <Button size="icon" variant="danger" onClick={() => void remove(host)} aria-label={`删除 ${host.name}`} title="删除节点">
                          <Trash2 size={16} />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {modalOpen && (
        <Modal
          title={editing ? `编辑节点 · ${editing.name}` : '新增 SSH 节点'}
          onClose={() => setModalOpen(false)}
          footer={(
            <>
              <Button variant="ghost" onClick={() => setModalOpen(false)}>取消</Button>
              <Button type="submit" form={FORM_ID} variant="primary">保存节点</Button>
            </>
          )}
        >
          <form id={FORM_ID} className="form-grid" onSubmit={save}>
            <TextField
              label="节点名称"
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
              required
            />
            {editing?.execution_mode === 'agent' ? (
              <div className="form-grid-wide agent-host-notice">
                <strong>Agent 管理节点</strong>
                <span>连接地址、运行用户和认证由 Agent 心跳维护；SSH 凭据已永久移除。</span>
              </div>
            ) : (
              <>
                <TextField label="主机地址" value={form.hostname} onChange={(event) => setForm({ ...form, hostname: event.target.value })} required />
                <TextField label="SSH 端口" type="number" min="1" max="65535" value={form.port} onChange={(event) => setForm({ ...form, port: event.target.value })} required />
                <TextField label="SSH 用户" value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} required />
                <SelectField label="认证方式" value={form.auth_type} onChange={(event) => setForm({ ...form, auth_type: event.target.value as HostForm['auth_type'] })}>
                  <option value="password">密码</option>
                  <option value="key">私钥路径</option>
                </SelectField>
                {form.auth_type === 'password' ? (
                  <TextField
                    label="SSH 密码"
                    type="password"
                    value={form.password}
                    placeholder={editing && !passwordRequired ? '留空保留原密码' : undefined}
                    onChange={(event) => setForm({ ...form, password: event.target.value })}
                    required={passwordRequired}
                  />
                ) : (
                  <TextField
                    label="服务器私钥路径"
                    value={form.private_key_path}
                    placeholder="/home/monitor/.ssh/id_ed25519"
                    onChange={(event) => setForm({ ...form, private_key_path: event.target.value })}
                    required
                  />
                )}
              </>
            )}
            <SelectField
              label="定时规则"
              value={form.enabled ? 'interval' : 'none'}
              onChange={(event) => setForm({ ...form, enabled: event.target.value === 'interval' })}
            >
              <option value="none">关闭</option>
              <option value="interval">固定间隔</option>
            </SelectField>
            {form.enabled && (
              <TextField
                label="探活间隔（秒）"
                type="number"
                min="60"
                value={form.check_interval}
                onChange={(event) => setForm({ ...form, check_interval: event.target.value })}
                required
              />
            )}
            <AlertTargetPicker
              label="节点告警目标（可多选）"
              configs={alertConfigs}
              selectedIds={form.alert_config_ids}
              onToggle={toggleAlert}
            />
          </form>
        </Modal>
      )}
    </>
  )
}
