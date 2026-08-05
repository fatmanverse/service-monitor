import { useEffect, useState } from 'react'
import { FolderKanban, Plus, Trash2 } from 'lucide-react'
import { api, errorMessage } from '../api'
import type { ResourceGroup, Service } from '../types'
import { Button } from '../ui/Button'
import { EmptyState, Notice, PageHeader } from '../ui/Display'
import { TextareaField, TextField } from '../ui/Field'
import { Modal } from '../ui/Modal'

const CREATE_FORM_ID = 'create-resource-group-form'
const ASSIGN_FORM_ID = 'assign-resource-group-form'

export function ResourceGroupsPage() {
  const [groups, setGroups] = useState<ResourceGroup[]>([])
  const [services, setServices] = useState<Service[]>([])
  const [createOpen, setCreateOpen] = useState(false)
  const [assignGroup, setAssignGroup] = useState<ResourceGroup | null>(null)
  const [selectedServices, setSelectedServices] = useState<number[]>([])
  const [form, setForm] = useState({ name: '', description: '' })
  const [message, setMessage] = useState('')

  async function load() {
    const [groupItems, serviceItems] = await Promise.all([api.resourceGroups(), api.services()])
    setGroups(groupItems)
    setServices(serviceItems)
  }

  useEffect(() => {
    load().catch((error) => setMessage(errorMessage(error)))
  }, [])

  async function create(event: React.FormEvent) {
    event.preventDefault()
    try {
      await api.createResourceGroup(form)
      setCreateOpen(false)
      setForm({ name: '', description: '' })
      await load()
    } catch (error) {
      setMessage(errorMessage(error))
    }
  }

  function openAssign(group: ResourceGroup) {
    setSelectedServices(
      services.filter((service) => service.resource_group_id === group.id).map((service) => service.id),
    )
    setAssignGroup(group)
  }

  async function assign(event: React.FormEvent) {
    event.preventDefault()
    if (!assignGroup) return
    try {
      const moving = services.filter(
        (service) => selectedServices.includes(service.id) && service.resource_group_id !== assignGroup.id,
      )
      await Promise.all(
        moving.map((service) => api.updateService(service.id, { resource_group_id: assignGroup.id })),
      )
      setAssignGroup(null)
      await load()
      setMessage('服务已移动到资源组')
    } catch (error) {
      setMessage(errorMessage(error))
    }
  }

  async function remove(group: ResourceGroup) {
    if (!confirm(`确认删除资源组“${group.name}”？`)) return
    try {
      await api.deleteResourceGroup(group.id)
      await load()
    } catch (error) {
      setMessage(errorMessage(error))
    }
  }

  return (
    <>
      <PageHeader
        title="资源组"
        description="将服务归入唯一资源组，再以资源组为单位授权用户。"
        actions={(
          <Button variant="primary" icon={<Plus size={16} />} onClick={() => setCreateOpen(true)}>
            新增资源组
          </Button>
        )}
      />
      {message && <Notice>{message}</Notice>}
      <section className="card-grid">
        {groups.length === 0 ? (
          <div className="ui-card card-grid-full">
            <EmptyState
              icon={<FolderKanban size={20} />}
              title="暂无资源组"
              description="创建资源组后再新增服务。"
            />
          </div>
        ) : groups.map((group) => (
          <article className="entity-card" key={group.id}>
            <header className="entity-card-head">
              <div className="entity-card-icon"><FolderKanban size={18} /></div>
              <div className="entity-card-title">
                <h2>{group.name}</h2>
                <p title={group.description || undefined}>{group.description || '未填写说明'}</p>
              </div>
            </header>
            <dl className="entity-metrics">
              <div><dt>服务</dt><dd>{group.service_count}</dd></div>
              <div><dt>用户</dt><dd>{group.user_count}</dd></div>
            </dl>
            <footer className="entity-card-footer">
              <Button size="sm" variant="ghost" onClick={() => openAssign(group)}>分配服务</Button>
              <Button
                size="icon"
                variant="danger"
                disabled={group.service_count > 0}
                onClick={() => void remove(group)}
                aria-label={`删除 ${group.name}`}
                title={group.service_count > 0 ? '请先移动组内服务' : '删除资源组'}
              >
                <Trash2 size={16} />
              </Button>
            </footer>
          </article>
        ))}
      </section>

      {createOpen && (
        <Modal
          title="新增资源组"
          onClose={() => setCreateOpen(false)}
          footer={(
            <>
              <Button variant="ghost" onClick={() => setCreateOpen(false)}>取消</Button>
              <Button type="submit" form={CREATE_FORM_ID} variant="primary">创建资源组</Button>
            </>
          )}
        >
          <form id={CREATE_FORM_ID} className="form-grid" onSubmit={create}>
            <TextField
              label="名称"
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
              required
            />
            <TextareaField
              label="说明"
              value={form.description}
              wide
              onChange={(event) => setForm({ ...form, description: event.target.value })}
            />
          </form>
        </Modal>
      )}

      {assignGroup && (
        <Modal
          title={`分配服务 · ${assignGroup.name}`}
          onClose={() => setAssignGroup(null)}
          footer={(
            <>
              <Button variant="ghost" onClick={() => setAssignGroup(null)}>取消</Button>
              <Button type="submit" form={ASSIGN_FORM_ID} variant="primary">移动选中服务</Button>
            </>
          )}
        >
          <form id={ASSIGN_FORM_ID} onSubmit={assign}>
            <div className="option-list">
              {services.length === 0 ? (
                <span className="option-empty">暂无可分配的服务。</span>
              ) : services.map((service) => (
                <label className="option-item" key={service.id}>
                  <input
                    type="checkbox"
                    checked={selectedServices.includes(service.id)}
                    disabled={service.resource_group_id === assignGroup.id}
                    onChange={(event) => setSelectedServices(
                      event.target.checked
                        ? [...selectedServices, service.id]
                        : selectedServices.filter((id) => id !== service.id),
                    )}
                  />
                  <span className="option-item-text">
                    <strong>{service.name}</strong>
                    <small>{service.resource_group_name} · {service.host_name}</small>
                  </span>
                </label>
              ))}
            </div>
          </form>
        </Modal>
      )}
    </>
  )
}
