import { useEffect, useState } from 'react'
import { BellRing, Pencil, Plus, Send, Trash2 } from 'lucide-react'
import { api, errorMessage } from '../api'
import { validateAlertForm, type AlertFormField, type FieldErrors } from '../lib/validation'
import type { AlertConfig } from '../types'
import { Tag } from '../ui/Badge'
import { Button } from '../ui/Button'
import { EmptyState, Notice, PageHeader } from '../ui/Display'
import { CheckboxField, TextField } from '../ui/Field'
import { Modal } from '../ui/Modal'

type AlertForm = {
  name: string
  webhook_url: string
  enabled: boolean
}

const FORM_ID = 'alert-config-form'
const blankForm = (): AlertForm => ({ name: '', webhook_url: '', enabled: true })

export function AlertsPage() {
  const [configs, setConfigs] = useState<AlertConfig[]>([])
  const [editing, setEditing] = useState<AlertConfig | null>(null)
  const [form, setForm] = useState<AlertForm>(blankForm())
  const [modalOpen, setModalOpen] = useState(false)
  const [formErrors, setFormErrors] = useState<FieldErrors<AlertFormField>>({})
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
    setFormErrors({})
    setModalOpen(true)
  }

  function openEdit(config: AlertConfig) {
    setEditing(config)
    setForm({ name: config.name, webhook_url: '', enabled: config.enabled })
    setFormErrors({})
    setModalOpen(true)
  }

  async function save(event: React.FormEvent) {
    event.preventDefault()
    setMessage('')
    const nextErrors = validateAlertForm(form, editing == null)
    setFormErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) return
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

  return (
    <>
      <PageHeader
        title="告警管理"
        description="维护多个飞书机器人，由服务选择需要通知的目标。"
        actions={(
          <Button variant="primary" icon={<Plus size={16} />} onClick={openCreate}>
            新增告警
          </Button>
        )}
      />
      {message && <Notice>{message}</Notice>}
      <section className="card-grid">
        {configs.length === 0 ? (
          <div className="ui-card card-grid-full">
            <EmptyState
              icon={<BellRing size={20} />}
              title="没有告警配置"
              description="新增飞书机器人后，可在服务配置中多选通知目标。"
            />
          </div>
        ) : configs.map((config) => (
          <article className="entity-card" key={config.id}>
            <header className="entity-card-head">
              <div className="entity-card-icon"><BellRing size={18} /></div>
              <div className="entity-card-title">
                <h2>{config.name}</h2>
                <p>{config.webhook_configured ? 'Webhook 已配置' : 'Webhook 未配置'}</p>
              </div>
              <Tag tone={config.enabled ? 'success' : 'danger'}>{config.enabled ? '启用' : '停用'}</Tag>
            </header>
            <dl className="entity-metrics">
              <div><dt>节点</dt><dd>{config.host_count}</dd></div>
              <div><dt>服务</dt><dd>{config.service_count}</dd></div>
            </dl>
            <footer className="entity-card-footer">
              <Button
                size="sm"
                variant="ghost"
                icon={<Send size={15} />}
                loading={busyId === config.id}
                disabled={!config.webhook_configured}
                onClick={() => void test(config)}
              >
                测试
              </Button>
              <Button size="sm" variant="ghost" icon={<Pencil size={15} />} onClick={() => openEdit(config)}>
                编辑
              </Button>
              <Button
                size="icon"
                variant="danger"
                onClick={() => void remove(config)}
                aria-label={`删除 ${config.name}`}
                title="删除告警"
              >
                <Trash2 size={16} />
              </Button>
            </footer>
          </article>
        ))}
      </section>

      {modalOpen && (
        <Modal
          title={editing ? `编辑告警 · ${editing.name}` : '新增飞书告警'}
          onClose={() => setModalOpen(false)}
          footer={(
            <>
              <Button variant="ghost" onClick={() => setModalOpen(false)}>取消</Button>
              <Button type="submit" form={FORM_ID} variant="primary">保存告警</Button>
            </>
          )}
        >
          <form id={FORM_ID} className="form-grid" onSubmit={save} noValidate>
            <TextField
              label="告警名称"
              value={form.name}
              wide
              error={formErrors.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
            />
            <TextField
              label="Webhook 地址"
              value={form.webhook_url}
              wide
              error={formErrors.webhook_url}
              hint={editing?.webhook_configured ? '留空将保留原地址。' : undefined}
              placeholder={editing?.webhook_configured ? '已配置，留空保留' : 'https://open.feishu.cn/open-apis/bot/v2/hook/...'}
              onChange={(event) => setForm({ ...form, webhook_url: event.target.value })}
            />
            <CheckboxField
              label="启用告警"
              checked={form.enabled}
              onChange={(event) => setForm({ ...form, enabled: event.target.checked })}
            />
          </form>
        </Modal>
      )}
    </>
  )
}
