import { useCallback, useEffect, useState } from 'react'
import { api, clearToken, getToken, setUnauthorizedHandler } from './api'
import { AppShell } from './app/AppShell'
import { LoginPage } from './app/LoginPage'
import { resolveSection, type SectionId } from './app/navigation'
import { useHashRoute } from './hooks/useHashRoute'
import { AgentsPage } from './pages/AgentsPage'
import { AlertsPage } from './pages/AlertsPage'
import { HostsPage } from './pages/HostsPage'
import { ResourceGroupsPage } from './pages/ResourceGroupsPage'
import { ServicesPage } from './pages/ServicesPage'
import { UsersPage } from './pages/UsersPage'
import { ToastProvider } from './ui/Toast'
import type { User } from './types'

function SectionView({ section, user }: { section: SectionId; user: User }) {
  switch (section) {
    case 'hosts':
      return <HostsPage />
    case 'agents':
      return <AgentsPage />
    case 'resources':
      return <ResourceGroupsPage />
    case 'alerts':
      return <AlertsPage />
    case 'users':
      return <UsersPage currentUserId={user.id} />
    case 'services':
      return <ServicesPage isAdmin={user.is_admin} />
  }
}

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [restoring, setRestoring] = useState(Boolean(getToken()))
  const { hash, navigate } = useHashRoute()

  const logout = useCallback(() => {
    clearToken()
    setUser(null)
  }, [])

  // Any 401 on an authenticated request drops straight back to the login view.
  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null))
    return () => setUnauthorizedHandler(null)
  }, [])

  useEffect(() => {
    if (!getToken()) return
    let cancelled = false
    api
      .me()
      .then((currentUser) => {
        if (!cancelled) setUser(currentUser)
      })
      .catch(() => clearToken())
      .finally(() => {
        if (!cancelled) setRestoring(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (restoring) return <div className="loading-screen">正在加载控制台…</div>
  if (!user) return <LoginPage onLogin={setUser} />

  const section = resolveSection(hash, user.is_admin)

  return (
    <ToastProvider>
      <AppShell user={user} section={section} onNavigate={navigate} onLogout={logout}>
        {/* Keying on the section discards stale page state and pollers on navigation. */}
        <SectionView key={section} section={section} user={user} />
      </AppShell>
    </ToastProvider>
  )
}
