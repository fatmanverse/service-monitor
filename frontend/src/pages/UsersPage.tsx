import { useEffect, useState } from 'react'
import { KeyRound, Plus, Trash2, Users } from 'lucide-react'
import { api, errorMessage } from '../api'
import { EmptyState, Modal, PageHeader } from '../components'
import type { ResourceGroup, User } from '../types'

export function UsersPage({ currentUserId }: { currentUserId: number }) {
  const [users, setUsers] = useState<User[]>([])
  const [groups, setGroups] = useState<ResourceGroup[]>([])
  const [createOpen, setCreateOpen] = useState(false)
  const [grantUser, setGrantUser] = useState<User | null>(null)
  const [selected, setSelected] = useState<number[]>([])
  const [form, setForm] = useState({ username: '', password: '', is_admin: false })
  const [message, setMessage] = useState('')
  async function load() { const [userItems, groupItems] = await Promise.all([api.users(), api.resourceGroups()]); setUsers(userItems); setGroups(groupItems) }
  useEffect(() => { load().catch((error) => setMessage(errorMessage(error))) }, [])
  async function create(event: React.FormEvent) { event.preventDefault(); try { await api.createUser({ ...form, is_active: true }); setCreateOpen(false); setForm({ username: '', password: '', is_admin: false }); await load() } catch (error) { setMessage(errorMessage(error)) } }
  async function openGrants(user: User) { try { const grants = await api.userResourceGroups(user.id); setSelected(grants.map((group) => group.id)); setGrantUser(user) } catch (error) { setMessage(errorMessage(error)) } }
  async function saveGrants(event: React.FormEvent) { event.preventDefault(); if (!grantUser) return; try { await api.setUserResourceGroups(grantUser.id, selected); setGrantUser(null); setMessage('资源组可见范围已更新'); await load() } catch (error) { setMessage(errorMessage(error)) } }
  async function remove(user: User) { if (!confirm(`确认删除用户“${user.username}”？`)) return; try { await api.deleteUser(user.id); await load() } catch (error) { setMessage(errorMessage(error)) } }
  return <>
    <PageHeader eyebrow="ACCESS CONTROL" title="用户管理" description="管理员创建账号，并按资源组分配服务可见范围。" action={<button className="primary-button" onClick={() => setCreateOpen(true)}><Plus size={18} />新增用户</button>} />
    {message && <div className="notice">{message}</div>}
    <section className="data-card">{users.length === 0 ? <EmptyState title="暂无用户" description="创建账号后分配资源组访问范围。" /> : <div className="table-scroll"><table><thead><tr><th>用户</th><th>角色</th><th>状态</th><th>创建时间</th><th>操作</th></tr></thead><tbody>{users.map((user) => <tr key={user.id}><td><div className="primary-cell"><Users size={18} /><strong>{user.username}</strong></div></td><td>{user.is_admin ? '管理员' : '普通用户'}</td><td>{user.is_active ? '启用' : '停用'}</td><td>{new Date(user.created_at).toLocaleString()}</td><td><div className="row-actions">{!user.is_admin && <button className="ghost-button" onClick={() => openGrants(user)}><KeyRound size={16} />分配资源组</button>}<button className="danger-button" disabled={user.id === currentUserId} onClick={() => remove(user)}><Trash2 size={16} /></button></div></td></tr>)}</tbody></table></div>}</section>
    {createOpen && <Modal title="新增用户" onClose={() => setCreateOpen(false)}><form className="form-grid" onSubmit={create}><label>用户名<input value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} minLength={3} required /></label><label>密码<input type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} minLength={8} required /></label><label className="checkbox-label"><input type="checkbox" checked={form.is_admin} onChange={(event) => setForm({ ...form, is_admin: event.target.checked })} />设为管理员</label><div className="form-actions"><button type="button" className="secondary-button" onClick={() => setCreateOpen(false)}>取消</button><button className="primary-button">创建用户</button></div></form></Modal>}
    {grantUser && <Modal title={`分配资源组 · ${grantUser.username}`} onClose={() => setGrantUser(null)}><form onSubmit={saveGrants}><div className="grant-list">{groups.map((group) => <label key={group.id}><input type="checkbox" checked={selected.includes(group.id)} onChange={(event) => setSelected(event.target.checked ? [...selected, group.id] : selected.filter((id) => id !== group.id))} /><span><strong>{group.name}</strong><small>{group.service_count} 个服务 · {group.description || '无说明'}</small></span></label>)}</div><div className="form-actions"><button type="button" className="secondary-button" onClick={() => setGrantUser(null)}>取消</button><button className="primary-button">保存权限</button></div></form></Modal>}
  </>
}
