import { useEffect, useState } from 'react'
import {
  BellRing,
  FolderKanban,
  LogOut,
  Menu,
  Server,
  ShieldCheck,
  Users,
  X,
} from 'lucide-react'
import { api, clearToken, getToken, setToken } from './api'
import { AlertsPage } from './pages/AlertsPage'
import { HostsPage } from './pages/HostsPage'
import { ResourceGroupsPage } from './pages/ResourceGroupsPage'
import { ServicesPage } from './pages/ServicesPage'
import { UsersPage } from './pages/UsersPage'
import type { User } from './types'

type Section = 'hosts' | 'resources' | 'services' | 'alerts' | 'users'

const adminNavigation = [
  { id: 'hosts' as const, label: '主机管理', icon: Server },
  { id: 'resources' as const, label: '资源组', icon: FolderKanban },
  { id: 'services' as const, label: '服务监测', icon: ShieldCheck },
  { id: 'alerts' as const, label: '告警管理', icon: BellRing },
  { id: 'users' as const, label: '用户管理', icon: Users },
]

function Login({ onLogin }: { onLogin: (user: User) => void }) {
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      const token = await api.login(username, password)
      setToken(token.access_token)
      onLogin(await api.me())
    } catch (requestError) {
      clearToken()
      setError(requestError instanceof Error ? requestError.message : '登录失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="login-page">
      <section className="login-panel">
        <div className="brand-mark"><ShieldCheck size={28} /></div>
        <span className="eyebrow">SERVICE OPERATIONS</span>
        <h1>服务监控中心</h1>
        <p>统一管理节点、探活策略、故障拉起与服务告警。</p>
        <form onSubmit={submit} className="login-form">
          <label>用户名<input value={username} onChange={(event) => setUsername(event.target.value)} required /></label>
          <label>密码<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required /></label>
          {error && <div className="form-error">{error}</div>}
          <button className="primary-button" disabled={submitting}>{submitting ? '登录中…' : '进入控制台'}</button>
        </form>
      </section>
      <aside className="login-aside">
        <span>01</span>
        <strong>将故障发现和恢复动作放在同一个控制面。</strong>
        <p>最小探活周期 60 秒，适用于 200 台主机与 1000 个服务的单机运维场景。</p>
      </aside>
    </main>
  )
}

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [section, setSection] = useState<Section>('services')
  const [loading, setLoading] = useState(Boolean(getToken()))
  const [sidebarOpen, setSidebarOpen] = useState(false)

  useEffect(() => {
    if (!getToken()) return
    api.me()
      .then((currentUser) => {
        setUser(currentUser)
        setSection(currentUser.is_admin ? 'hosts' : 'services')
      })
      .catch(() => clearToken())
      .finally(() => setLoading(false))
  }, [])

  function logout() {
    clearToken()
    setUser(null)
  }

  if (loading) return <div className="loading-screen">正在加载控制台…</div>
  if (!user) return <Login onLogin={(currentUser) => { setUser(currentUser); setSection(currentUser.is_admin ? 'hosts' : 'services') }} />

  const navigation = user.is_admin ? adminNavigation : adminNavigation.filter((item) => item.id === 'services')
  return (
    <div className="app-shell">
      <button className="mobile-menu" onClick={() => setSidebarOpen(true)} aria-label="打开菜单"><Menu /></button>
      <aside className={`sidebar ${sidebarOpen ? 'sidebar-open' : ''}`}>
        <div className="sidebar-brand"><div className="brand-mark"><ShieldCheck size={22} /></div><div><strong>服务监控</strong><span>CONTROL CENTER</span></div></div>
        <button className="sidebar-close" onClick={() => setSidebarOpen(false)} aria-label="关闭菜单"><X /></button>
        <nav>
          {navigation.map((item, index) => {
            const Icon = item.icon
            return <button key={item.id} className={section === item.id ? 'active' : ''} onClick={() => { setSection(item.id); setSidebarOpen(false) }}><span className="nav-index">0{index + 1}</span><Icon size={19} /><span>{item.label}</span></button>
          })}
        </nav>
        <div className="sidebar-footer">
          <div className="user-chip"><span>{user.username.slice(0, 1).toUpperCase()}</span><div><strong>{user.username}</strong><small>{user.is_admin ? '管理员' : '服务查看者'}</small></div></div>
          <button className="icon-button" onClick={logout} aria-label="退出登录"><LogOut size={18} /></button>
        </div>
      </aside>
      {sidebarOpen && <div className="sidebar-scrim" onClick={() => setSidebarOpen(false)} />}
      <main className="content">
        {section === 'hosts' && user.is_admin && <HostsPage />}
        {section === 'resources' && user.is_admin && <ResourceGroupsPage />}
        {section === 'services' && <ServicesPage isAdmin={user.is_admin} />}
        {section === 'alerts' && user.is_admin && <AlertsPage />}
        {section === 'users' && user.is_admin && <UsersPage currentUserId={user.id} />}
      </main>
    </div>
  )
}
