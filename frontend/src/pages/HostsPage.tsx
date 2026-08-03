import { useEffect, useState } from 'react'
import { Activity, Plus, Server, Trash2 } from 'lucide-react'
import { api, errorMessage } from '../api'
import { EmptyState, Modal, PageHeader, StatusBadge } from '../components'
import type { Host } from '../types'

const initialForm = { name: '', hostname: '', port: '22', username: '', auth_type: 'password', password: '', private_key_path: '', check_interval: '60', enabled: true }

export function HostsPage() {
  const [hosts, setHosts] = useState<Host[]>([])
  const [modalOpen, setModalOpen] = useState(false)
  const [form, setForm] = useState(initialForm)
  const [message, setMessage] = useState('')
  const [busyId, setBusyId] = useState<number | null>(null)

  async function load() { setHosts(await api.hosts()) }
  useEffect(() => { load().catch((error) => setMessage(errorMessage(error))) }, [])

  async function create(event: React.FormEvent) {
    event.preventDefault()
    setMessage('')
    try {
      await api.createHost({ ...form, port: Number(form.port), check_interval: Number(form.check_interval), password: form.auth_type === 'password' ? form.password : null, private_key_path: form.auth_type === 'key' ? form.private_key_path : null })
      setModalOpen(false); setForm(initialForm); await load()
    } catch (error) { setMessage(errorMessage(error)) }
  }

  async function probe(host: Host) {
    setBusyId(host.id); setMessage('')
    try { const result = await api.probeHost(host.id); setMessage(`${host.name}：${result.message}`); await load() }
    catch (error) { setMessage(errorMessage(error)) } finally { setBusyId(null) }
  }

  async function remove(host: Host) {
    if (!confirm(`删除主机“${host.name}”将同时删除其所有服务监测，确认继续？`)) return
    try { await api.deleteHost(host.id); await load() } catch (error) { setMessage(errorMessage(error)) }
  }

  return <>
    <PageHeader eyebrow="INFRASTRUCTURE" title="主机管理" description="维护 SSH 节点连接与主机级定时探活。" action={<button className="primary-button" onClick={() => setModalOpen(true)}><Plus size={18} />新增节点</button>} />
    {message && <div className="notice">{message}</div>}
    <div className="metric-strip"><div><span>节点总数</span><strong>{hosts.length}</strong></div><div><span>在线</span><strong>{hosts.filter((item) => item.status === 'online').length}</strong></div><div><span>离线</span><strong>{hosts.filter((item) => item.status === 'offline').length}</strong></div></div>
    <section className="data-card">
      {hosts.length === 0 ? <EmptyState title="尚未添加节点" description="新增第一个 SSH 节点后即可配置服务监测。" /> : <div className="table-scroll"><table><thead><tr><th>节点</th><th>SSH 地址</th><th>认证</th><th>周期</th><th>状态</th><th>最后检查</th><th>操作</th></tr></thead><tbody>{hosts.map((host) => <tr key={host.id}><td><div className="primary-cell"><Server size={18} /><div><strong>{host.name}</strong><span>{host.username}</span></div></div></td><td className="mono">{host.hostname}:{host.port}</td><td>{host.auth_type === 'password' ? '密码' : '私钥'}</td><td>{host.check_interval}s</td><td><StatusBadge status={host.status} /></td><td>{host.last_checked_at ? new Date(host.last_checked_at).toLocaleString() : '尚未检查'}</td><td><div className="row-actions"><button className="ghost-button" disabled={busyId === host.id} onClick={() => probe(host)}><Activity size={16} />探活</button><button className="danger-button" onClick={() => remove(host)}><Trash2 size={16} /></button></div></td></tr>)}</tbody></table></div>}
    </section>
    {modalOpen && <Modal title="新增 SSH 节点" onClose={() => setModalOpen(false)}><form className="form-grid" onSubmit={create}>
      <label>节点名称<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></label><label>主机地址<input value={form.hostname} onChange={(e) => setForm({ ...form, hostname: e.target.value })} required /></label><label>SSH 端口<input type="number" value={form.port} onChange={(e) => setForm({ ...form, port: e.target.value })} required /></label><label>SSH 用户<input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required /></label><label>认证方式<select value={form.auth_type} onChange={(e) => setForm({ ...form, auth_type: e.target.value })}><option value="password">密码</option><option value="key">私钥路径</option></select></label>{form.auth_type === 'password' ? <label>SSH 密码<input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required /></label> : <label>服务器私钥路径<input value={form.private_key_path} onChange={(e) => setForm({ ...form, private_key_path: e.target.value })} placeholder="/home/monitor/.ssh/id_ed25519" required /></label>}<label>探活周期（秒）<input type="number" min="60" value={form.check_interval} onChange={(e) => setForm({ ...form, check_interval: e.target.value })} required /></label><label className="checkbox-label"><input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />启用定时探活</label><div className="form-actions"><button type="button" className="secondary-button" onClick={() => setModalOpen(false)}>取消</button><button className="primary-button">保存节点</button></div>
    </form></Modal>}
  </>
}
