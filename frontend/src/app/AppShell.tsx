import { useEffect, useState } from 'react'
import { LogOut, Menu, Moon, ShieldCheck, Sun, X } from 'lucide-react'
import { Button } from '../ui/Button'
import { useTheme } from '../hooks/useTheme'
import {
  NAVIGATION_GROUPS,
  sectionLabel,
  visibleNavigation,
  type SectionId,
} from './navigation'
import type { User } from '../types'

interface AppShellProps {
  user: User
  section: SectionId
  onNavigate: (section: SectionId) => void
  onLogout: () => void
  children: React.ReactNode
}

export function AppShell({ user, section, onNavigate, onLogout, children }: AppShellProps) {
  const { theme, toggleTheme } = useTheme()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const navigation = visibleNavigation(user.is_admin)

  // Close the mobile drawer whenever the route changes.
  useEffect(() => {
    setSidebarOpen(false)
  }, [section])

  useEffect(() => {
    if (!sidebarOpen) return
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setSidebarOpen(false)
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [sidebarOpen])

  return (
    <div className="app-shell">
      <aside className="sidebar" data-open={sidebarOpen || undefined}>
        <div className="sidebar-brand">
          <div className="brand-mark">
            <ShieldCheck size={20} />
          </div>
          <div className="sidebar-brand-text">
            <strong>服务监控</strong>
            <span>Control Center</span>
          </div>
        </div>
        <span className="sidebar-close">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setSidebarOpen(false)}
            aria-label="关闭菜单"
          >
            <X size={18} />
          </Button>
        </span>

        <nav className="sidebar-nav" aria-label="主导航">
          {NAVIGATION_GROUPS.map((group) => {
            const items = navigation.filter((item) => item.group === group)
            if (items.length === 0) return null
            return (
              <div key={group}>
                <div className="sidebar-nav-label">{group}</div>
                {items.map((item) => {
                  const Icon = item.icon
                  return (
                    <button
                      key={item.id}
                      type="button"
                      aria-current={section === item.id ? 'page' : undefined}
                      onClick={() => onNavigate(item.id)}
                    >
                      <Icon size={18} />
                      <span>{item.label}</span>
                    </button>
                  )
                })}
              </div>
            )
          })}
        </nav>

        <div className="sidebar-footer">
          <div className="user-chip">
            <span className="user-avatar">{user.username.slice(0, 1).toUpperCase()}</span>
            <div className="user-chip-text">
              <strong>{user.username}</strong>
              <span>{user.is_admin ? '管理员' : '服务查看者'}</span>
            </div>
          </div>
          <Button variant="ghost" size="icon" onClick={onLogout} aria-label="退出登录" title="退出登录">
            <LogOut size={17} />
          </Button>
        </div>
      </aside>

      {sidebarOpen && (
        <div className="sidebar-scrim" role="presentation" onClick={() => setSidebarOpen(false)} />
      )}

      <div className="main-column">
        <header className="topbar">
          <span className="mobile-menu">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setSidebarOpen(true)}
              aria-label="打开菜单"
            >
              <Menu size={18} />
            </Button>
          </span>
          <h2 className="topbar-title">{sectionLabel(section)}</h2>
          <div className="topbar-spacer" />
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleTheme}
            aria-label={theme === 'dark' ? '切换到亮色主题' : '切换到暗色主题'}
            title={theme === 'dark' ? '切换到亮色主题' : '切换到暗色主题'}
          >
            {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
          </Button>
        </header>
        <main className="content">{children}</main>
      </div>
    </div>
  )
}
