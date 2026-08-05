import { useEffect, useState } from 'react'
import { KeyRound, Plus, Trash2, Users } from 'lucide-react'
import { api, errorMessage } from '../api'
import { formatDateTime } from '../lib/format'
import type { ResourceGroup, User } from '../types'
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
  const [createOpen, setCreateOpen] = useState(false)
  const [grantUser, setGrantUser] = useState<User | null>(null)
  const [selected, setSelected] = useState<number[]>([])
  const [form, setForm] = useState({ username: '', password: '', is_admin: false })
  const [message, setMessage] = useState('')

  async function load() {
    const [userItems, groupItems] = await Promise.all([api.users(), api.resourceGroups()])
    setUsers(userItems)
    setGroups(groupItems)
  }

  useEffect(() => {
    load().catch((error) => setMessage(errorMessage(error)))
  }, [])

  async function create(event: React.FormEvent) {
    event.preventDefault()
    try {
      await api.createUser({ ...form, is_active: true })
      setCreateOpen(false)
      setForm({ username: '', password: '', is_admin: false })
      await load()
    } catch (error) {
      setMessage(errorMessage(error))
    }
  }

  async function openGrants(user: User) {
    try {
      const grants = await api.userResourceGroups(user.id)
      setSelected(grants.map((group) => group.id))
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
      setGrantUser(null)
      setMessage('资源组可见范围已更新')
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
        description="管理员创建账号，并按资源组分配服务可见范围。"
        actions={(
          <Button variant="primary" icon={<Plus size={16} />} onClick={() => setCreateOpen(true)}>
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
                            分配资源组
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
              minLength={3}
              autoComplete="username"
              onChange={(event) => setForm({ ...form, username: event.target.value })}
              required
            />
            <TextField
              label="密码"
              type="password"
              value={form.password}
              minLength={8}
              autoComplete="new-password"
              onChange={(event) => setForm({ ...form, password: event.target.value })}
              required
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
          title={`分配资源组 · ${grantUser.username}`}
          onClose={() => setGrantUser(null)}
          footer={(
            <>
              <Button variant="ghost" onClick={() => setGrantUser(null)}>取消</Button>
              <Button type="submit" form={GRANT_FORM_ID} variant="primary">保存权限</Button>
            </>
          )}
        >
          <form id={GRANT_FORM_ID} onSubmit={saveGrants}>
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
          </form>
        </Modal>
      )}
    </>
  )
}
