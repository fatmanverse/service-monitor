import { useEffect, useState } from 'react'
import { KeyRound, Plus, Trash2, Users } from 'lucide-react'
import { api, errorMessage } from '../api'
import { formatDateTime } from '../lib/format'
import { validateUserForm, type FieldErrors, type UserFormField } from '../lib/validation'
import type { ResourceGroup, Service, User } from '../types'
import { Tag } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Card, EmptyState, Notice, PageHeader } from '../ui/Display'
import { CheckboxField, TextField } from '../ui/Field'
import { Modal } from '../ui/Modal'

const CREATE_FORM_ID = 'create-user-form'
const GRANT_FORM_ID = 'grant-user-form'

export function UsersPage({ currentUserId }: { currentUserId: number }) {
  const [users, setUsers] = useState<User[]>([])
  const [groups, setGroups] = useState<ResourceGroup[]>([])
  const [ungroupedServices, setUngroupedServices] = useState<Service[]>([])
  const [createOpen, setCreateOpen] = useState(false)
  const [grantUser, setGrantUser] = useState<User | null>(null)
  const [selected, setSelected] = useState<number[]>([])
  const [selectedServices, setSelectedServices] = useState<number[]>([])
  const [form, setForm] = useState({ username: '', password: '', is_admin: false })
  const [formErrors, setFormErrors] = useState<FieldErrors<UserFormField>>({})
  const [message, setMessage] = useState('')

  async function load() {
    const [userItems, groupItems, serviceItems] = await Promise.all([
      api.users(),
      api.resourceGroups(),
      api.services(),
    ])
    setUsers(userItems)
    setGroups(groupItems)
    setUngroupedServices(serviceItems.filter((service) => service.resource_group_id == null))
  }

  useEffect(() => {
    load().catch((error) => setMessage(errorMessage(error)))
  }, [])

  function openCreate() {
    setForm({ username: '', password: '', is_admin: false })
    setFormErrors({})
    setCreateOpen(true)
  }

  async function create(event: React.FormEvent) {
    event.preventDefault()
    const nextErrors = validateUserForm(form)
    setFormErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) return
    try {
      await api.createUser({ ...form, is_active: true })
      setCreateOpen(false)
      setForm({ username: '', password: '', is_admin: false })
      setFormErrors({})
      await load()
    } catch (error) {
      setMessage(errorMessage(error))
    }
  }

  async function openGrants(user: User) {
    try {
      const [groupGrants, serviceGrants] = await Promise.all([
        api.userResourceGroups(user.id),
        api.userServices(user.id),
      ])
      setSelected(groupGrants.map((group) => group.id))
      setSelectedServices(serviceGrants.map((service) => service.id))
      setGrantUser(user)
    } catch (error) {
      setMessage(errorMessage(error))
    }
  }

  async function saveGrants(event: React.FormEvent) {
    event.preventDefault()
    if (!grantUser) return
    try {
      await api.setUserResourceGroups(grantUser.id, selected)
      await api.setUserServices(grantUser.id, selectedServices)
      setGrantUser(null)
      setMessage('可见范围已更新')
      await load()
    } catch (error) {
      setMessage(errorMessage(error))
    }
  }

  async function remove(user: User) {
    if (!confirm(`确认删除用户“${user.username}”？`)) return
    try {
      await api.deleteUser(user.id)
      await load()
    } catch (error) {
      setMessage(errorMessage(error))
    }
  }

  return (
    <>
      <PageHeader
        title="用户管理"
        description="管理员创建账号，按资源组或单个服务分配可见范围。"
        actions={(
          <Button variant="primary" icon={<Plus size={16} />} onClick={openCreate}>
            新增用户
          </Button>
        )}
      />
      {message && <Notice>{message}</Notice>}
      <Card>
        {users.length === 0 ? (
          <EmptyState
            icon={<Users size={20} />}
            title="暂无用户"
            description="创建账号后分配资源组访问范围。"
          />
        ) : (
          <div className="table-scroll">
            <table className="ui-table">
              <thead>
                <tr>
                  <th>用户</th>
                  <th>角色</th>
                  <th>状态</th>
                  <th>创建时间</th>
                  <th aria-label="操作" />
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id}>
                    <td>
                      <div className="cell-primary">
                        <span className="cell-icon"><Users size={16} /></span>
                        <span className="cell-primary-text"><strong>{user.username}</strong></span>
                      </div>
                    </td>
                    <td><Tag tone={user.is_admin ? 'success' : undefined}>{user.is_admin ? '管理员' : '普通用户'}</Tag></td>
                    <td><Tag tone={user.is_active ? 'success' : 'danger'}>{user.is_active ? '启用' : '停用'}</Tag></td>
                    <td className="cell-muted">{formatDateTime(user.created_at) ?? '—'}</td>
                    <td>
                      <div className="row-actions">
                        {!user.is_admin && (
                          <Button
                            size="sm"
                            variant="ghost"
                            icon={<KeyRound size={15} />}
                            onClick={() => void openGrants(user)}
                          >
                            分配可见范围
                          </Button>
                        )}
                        <Button
                          size="icon"
                          variant="danger"
                          disabled={user.id === currentUserId}
                          onClick={() => void remove(user)}
                          aria-label={`删除 ${user.username}`}
                          title={user.id === currentUserId ? '不能删除当前登录用户' : '删除用户'}
                        >
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

      {createOpen && (
        <Modal
          title="新增用户"
          onClose={() => setCreateOpen(false)}
          footer={(
            <>
              <Button variant="ghost" onClick={() => setCreateOpen(false)}>取消</Button>
              <Button type="submit" form={CREATE_FORM_ID} variant="primary">创建用户</Button>
            </>
          )}
        >
          <form id={CREATE_FORM_ID} className="form-grid" onSubmit={create}>
            <TextField
              label="用户名"
              value={form.username}
              error={formErrors.username}
              hint="3 到 64 个字符。"
              autoComplete="username"
              onChange={(event) => setForm({ ...form, username: event.target.value })}
            />
            <TextField
              label="密码"
              type="password"
              value={form.password}
              error={formErrors.password}
              hint="至少 8 个字符。"
              autoComplete="new-password"
              onChange={(event) => setForm({ ...form, password: event.target.value })}
            />
            <CheckboxField
              label="设为管理员"
              checked={form.is_admin}
              onChange={(event) => setForm({ ...form, is_admin: event.target.checked })}
            />
          </form>
        </Modal>
      )}

      {grantUser && (
        <Modal
          title={`分配可见范围 · ${grantUser.username}`}
          onClose={() => setGrantUser(null)}
          footer={(
            <>
              <Button variant="ghost" onClick={() => setGrantUser(null)}>取消</Button>
              <Button type="submit" form={GRANT_FORM_ID} variant="primary">保存权限</Button>
            </>
          )}
        >
          <form id={GRANT_FORM_ID} onSubmit={saveGrants}>
            <section className="form-section">
              <header className="form-section-head">
                <div>
                  <h3>资源组</h3>
                  <p>授予资源组后，该组内的所有服务都可见。</p>
                </div>
              </header>
              <div className="option-list">
                {groups.length === 0 ? (
                  <span className="option-empty">暂无可分配的资源组。</span>
                ) : groups.map((group) => (
                  <label className="option-item" key={group.id}>
                    <input
                      type="checkbox"
                      checked={selected.includes(group.id)}
                      onChange={(event) => setSelected(
                        event.target.checked
                          ? [...selected, group.id]
                          : selected.filter((id) => id !== group.id),
                      )}
                    />
                    <span className="option-item-text">
                      <strong>{group.name}</strong>
                      <small>{group.service_count} 个服务 · {group.description || '无说明'}</small>
                    </span>
                  </label>
                ))}
              </div>
            </section>

            <section className="form-section">
              <header className="form-section-head">
                <div>
                  <h3>未绑定资源组的服务</h3>
                  <p>这类服务没有所属资源组，只能在此逐个授权。</p>
                </div>
              </header>
              <div className="option-list">
                {ungroupedServices.length === 0 ? (
                  <span className="option-empty">暂无未绑定资源组的服务。</span>
                ) : ungroupedServices.map((service) => (
                  <label className="option-item" key={service.id}>
                    <input
                      type="checkbox"
                      checked={selectedServices.includes(service.id)}
                      onChange={(event) => setSelectedServices(
                        event.target.checked
                          ? [...selectedServices, service.id]
                          : selectedServices.filter((id) => id !== service.id),
                      )}
                    />
                    <span className="option-item-text">
                      <strong>{service.name}</strong>
                      <small>{service.host_name} · {service.probes.length} 个探活项</small>
                    </span>
                  </label>
                ))}
              </div>
            </section>
          </form>
        </Modal>
      )}
    </>
  )
}
