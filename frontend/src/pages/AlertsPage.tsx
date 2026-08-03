import { useEffect, useState } from 'react'
import { BellRing, Pencil, Plus, Send, Trash2 } from 'lucide-react'
import { api, errorMessage } from '../api'
import { EmptyState, Modal, PageHeader } from '../components'
import type { AlertConfig } from '../types'

type AlertForm = {
  name: string
  webhook_url: string
  enabled: boolean
}

const blankForm = (): AlertForm => ({ name: '', webhook_url: '', enabled: true })

export function AlertsPage() {
  const [configs, setConfigs] = useState<AlertConfig[]>([])
  const [editing, setEditing] = useState<AlertConfig | null>(null)
  const [form, setForm] = useState<AlertForm>(blankForm())
  const [modalOpen, setModalOpen] = useState(false)
  const [message, setMessage] = useState('')
  const [busyId, setBusyId] = useState<number | null>(null)

  async function load() {
    setConfigs(await api.alerts())
  }

  useEffect(() => {
    load().catch((error) => setMessage(errorMessage(error)))
  }, [])

  function openCreate() {
    setEditing(null)
    setForm(blankForm())
    setModalOpen(true)
  }

  function openEdit(config: AlertConfig) {
    setEditing(config)
    setForm({ name: config.name, webhook_url: '', enabled: config.enabled })
    setModalOpen(true)
  }

  async function save(event: React.FormEvent) {
    event.preventDefault()
    setMessage('')
    try {
      const payload = {
        name: form.name,
        enabled: form.enabled,
        webhook_url: form.webhook_url || (editing ? null : undefined),
      }
      if (editing) await api.updateAlert(editing.id, payload)
      else await api.createAlert(payload)
      setModalOpen(false)
      await load()
    } catch (error) {
      setMessage(errorMessage(error))
    }
  }

  async function test(config: AlertConfig) {
    setBusyId(config.id)
    setMessage('')
    try {
      const result = await api.testAlert(config.id)
      setMessage(`${config.name}：${result.message}`)
    } catch (error) {
      setMessage(errorMessage(error))
    } finally {
      setBusyId(null)
    }
  }

  async function remove(config: AlertConfig) {
    if (!confirm(`确认删除飞书告警“${config.name}”？关联服务将停止向该机器人发送告警。`)) return
    try {
      await api.deleteAlert(config.id)
      await load()
    } catch (error) {
      setMessage(errorMessage(error))
    }
  }

  return <>
    <PageHeader
      eyebrow="NOTIFICATION"
      title="告警管理"
      description="维护多个飞书机器人，由服务选择需要通知的目标。"
      action={<button className="primary-button" onClick={openCreate}><Plus size={18} />新增告警</button>}
    />
    {message && <div className="notice">{message}</div>}
    <section className="resource-grid">
      {configs.length === 0
        ? <div className="data-card full-span"><EmptyState title="没有告警配置" description="新增飞书机器人后，可在服务配置中多选通知目标。" /></div>
        : configs.map((config) => <article className="resource-card" key={config.id}>
          <header>
            <div className="service-icon"><BellRing size={20} /></div>
            <div><h2>{config.name}</h2><p>{config.webhook_configured ? 'Webhook 已配置' : 'Webhook 未配置'}</p></div>
          </header>
          <dl>
            <div><dt>状态</dt><dd>{config.enabled ? '启用' : '停用'}</dd></div>
            <div><dt>关联目标</dt><dd>{config.host_count} 节点 / {config.service_count} 服务</dd></div>
          </dl>
          <footer>
            <button className="ghost-button" disabled={busyId === config.id || !config.webhook_configured} onClick={() => test(config)}><Send size={16} />测试</button>
            <button className="ghost-button" onClick={() => openEdit(config)}><Pencil size={16} />编辑</button>
            <button className="danger-button" onClick={() => remove(config)}><Trash2 size={16} /></button>
          </footer>
        </article>)}
    </section>
    {modalOpen && <Modal title={editing ? `编辑告警 · ${editing.name}` : '新增飞书告警'} onClose={() => setModalOpen(false)}>
      <form className="form-grid" onSubmit={save}>
        <label className="wide-field">告警名称<input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required /></label>
        <label className="wide-field">Webhook 地址<input type="url" value={form.webhook_url} onChange={(event) => setForm({ ...form, webhook_url: event.target.value })} placeholder={editing?.webhook_configured ? '留空保留原地址' : 'https://open.feishu.cn/open-apis/bot/v2/hook/...'} required={!editing} /></label>
        <label className="checkbox-label"><input type="checkbox" checked={form.enabled} onChange={(event) => setForm({ ...form, enabled: event.target.checked })} />启用告警</label>
        <div className="form-actions"><button type="button" className="secondary-button" onClick={() => setModalOpen(false)}>取消</button><button className="primary-button">保存告警</button></div>
      </form>
    </Modal>}
  </>
}
