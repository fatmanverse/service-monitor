import { BellRing, FolderKanban, Server, ShieldCheck, Users } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

export type SectionId = 'hosts' | 'resources' | 'services' | 'alerts' | 'users'

interface NavigationItem {
  id: SectionId
  label: string
  icon: LucideIcon
  adminOnly: boolean
}

export const NAVIGATION: NavigationItem[] = [
  { id: 'hosts', label: '主机管理', icon: Server, adminOnly: true },
  { id: 'resources', label: '资源组', icon: FolderKanban, adminOnly: true },
  { id: 'services', label: '服务监测', icon: ShieldCheck, adminOnly: false },
  { id: 'alerts', label: '告警管理', icon: BellRing, adminOnly: true },
  { id: 'users', label: '用户管理', icon: Users, adminOnly: true },
]

export function visibleNavigation(isAdmin: boolean) {
  return NAVIGATION.filter((item) => isAdmin || !item.adminOnly)
}

/** Admins land on hosts; viewers only ever have services. */
export function defaultSection(isAdmin: boolean): SectionId {
  return isAdmin ? 'hosts' : 'services'
}

/**
 * Resolves a raw hash segment to a section the current user may view. Unknown
 * values and admin-only sections requested by a viewer fall back to the
 * user's default section rather than rendering a blank page.
 */
export function resolveSection(hash: string, isAdmin: boolean): SectionId {
  const match = NAVIGATION.find((item) => item.id === hash)
  if (!match || (match.adminOnly && !isAdmin)) return defaultSection(isAdmin)
  return match.id
}
