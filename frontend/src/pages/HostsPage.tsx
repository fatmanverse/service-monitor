import { useEffect, useState } from 'react'
import { Activity, Pencil, Plus, Server, Trash2 } from 'lucide-react'
import { api, errorMessage } from '../api'
import { EmptyState, Modal, PageHeader, StatusBadge } from '../components'
import type { AlertConfig, Host } from '../types'

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

  useEffect(() => { load().catch((error) => setMessage(errorMessage(error))) }, [])

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

  return <>
    <PageHeader eyebrow="INFRASTRUCTURE" title="主机管理" description="维护 SSH 节点连接、主机级探活与节点状态告警。" action={<button className="primary-button" onClick={openCreate}><Plus size={18} />新增节点</button>} />
    {message && <div className="notice">{message}</div>}
    <div className="metric-strip"><div><span>节点总数</span><strong>{hosts.length}</strong></div><div><span>在线</span><strong>{hosts.filter((item) => item.status === 'online').length}</strong></div><div><span>离线</span><strong>{hosts.filter((item) => item.status === 'offline').length}</strong></div></div>
    <section className="data-card">
      {hosts.length === 0 ? <EmptyState title="尚未添加节点" description="新增 SSH 节点或批准 Agent 后即可配置服务监测。" /> : <div className="table-scroll"><table><thead><tr><th>节点</th><th>连接地址</th><th>执行模式</th><th>周期</th><th>告警目标</th><th>状态</th><th>最后检查</th><th>操作</th></tr></thead><tbody>{hosts.map((host) => <tr key={host.id}><td><div className="primary-cell"><Server size={18} /><div><strong>{host.name}</strong><span>{host.username}</span></div></div></td><td className="mono">{host.execution_mode === 'agent' ? host.hostname : `${host.hostname}:${host.port}`}</td><td><span className="mode-badge" data-mode={host.execution_mode}>{host.execution_mode === 'agent' ? 'Agent' : 'SSH'}</span></td><td>{host.enabled ? `${host.check_interval}s` : '关闭'}</td><td>{host.alert_configs.length}</td><td><StatusBadge status={host.status} /></td><td>{host.last_checked_at ? new Date(host.last_checked_at).toLocaleString() : '尚未检查'}</td><td><div className="row-actions">{host.execution_mode === 'ssh' && <button className="ghost-button" disabled={busyId === host.id} onClick={() => probe(host)}><Activity size={16} />探活</button>}<button className="ghost-button" onClick={() => openEdit(host)}><Pencil size={16} />编辑</button><button className="danger-button" onClick={() => remove(host)}><Trash2 size={16} /></button></div></td></tr>)}</tbody></table></div>}
    </section>
    {modalOpen && <Modal title={editing ? `编辑节点 · ${editing.name}` : '新增 SSH 节点'} onClose={() => setModalOpen(false)}><form className="form-grid" onSubmit={save}>
      <label>节点名称<input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required /></label>
      {editing?.execution_mode === 'agent' ? <div className="wide-field agent-host-notice"><strong>Agent 管理节点</strong><span>连接地址、运行用户和认证由 Agent 心跳维护；SSH 凭据已永久移除。</span></div> : <><label>主机地址<input value={form.hostname} onChange={(event) => setForm({ ...form, hostname: event.target.value })} required /></label><label>SSH 端口<input type="number" min="1" max="65535" value={form.port} onChange={(event) => setForm({ ...form, port: event.target.value })} required /></label><label>SSH 用户<input value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} required /></label><label>认证方式<select value={form.auth_type} onChange={(event) => setForm({ ...form, auth_type: event.target.value as HostForm['auth_type'] })}><option value="password">密码</option><option value="key">私钥路径</option></select></label>{form.auth_type === 'password' ? <label>SSH 密码<input type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} placeholder={editing && !passwordRequired ? '留空保留原密码' : ''} required={passwordRequired} /></label> : <label>服务器私钥路径<input value={form.private_key_path} onChange={(event) => setForm({ ...form, private_key_path: event.target.value })} placeholder="/home/monitor/.ssh/id_ed25519" required /></label>}</>}
      <label>定时规则<select value={form.enabled ? 'interval' : 'none'} onChange={(event) => setForm({ ...form, enabled: event.target.value === 'interval' })}><option value="none">关闭</option><option value="interval">固定间隔</option></select></label>
      {form.enabled && <label>探活间隔（秒）<input type="number" min="60" value={form.check_interval} onChange={(event) => setForm({ ...form, check_interval: event.target.value })} required /></label>}
      <div className="wide-field"><span className="field-label">节点告警目标（可多选）</span><div className="alert-target-list">{alertConfigs.length === 0 ? <span>暂无飞书告警配置，请先前往告警管理新增。</span> : alertConfigs.map((config) => { const selected = form.alert_config_ids.includes(config.id); return <label key={config.id}><input type="checkbox" checked={selected} disabled={!selected && (!config.enabled || !config.webhook_configured)} onChange={() => toggleAlert(config.id)} /><span><strong>{config.name}</strong><small>{config.enabled ? (config.webhook_configured ? '启用' : 'Webhook 未配置') : '已停用'}</small></span></label> })}</div></div>
      <div className="form-actions"><button type="button" className="secondary-button" onClick={() => setModalOpen(false)}>取消</button><button className="primary-button">保存节点</button></div>
    </form></Modal>}
  </>
}
