import { BellRing, CircleUserRound, Cpu, FolderKanban, Server, ShieldCheck, Users } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

export type SectionId = 'services' | 'hosts' | 'agents' | 'resources' | 'alerts' | 'users' | 'account'

export interface AppRoute {
  section: SectionId
  serviceId?: number
}

type NavigationGroup = '监控' | '配置'

interface NavigationItem {
  id: SectionId
  label: string
  icon: LucideIcon
  adminOnly: boolean
  group: NavigationGroup
}

const NAVIGATION: NavigationItem[] = [
  { id: 'services', label: '服务监测', icon: ShieldCheck, adminOnly: false, group: '监控' },
  { id: 'hosts', label: '主机管理', icon: Server, adminOnly: true, group: '监控' },
  { id: 'agents', label: 'Agent 接入', icon: Cpu, adminOnly: true, group: '监控' },
  { id: 'resources', label: '资源组', icon: FolderKanban, adminOnly: true, group: '配置' },
  { id: 'alerts', label: '告警管理', icon: BellRing, adminOnly: true, group: '配置' },
  { id: 'users', label: '用户管理', icon: Users, adminOnly: true, group: '配置' },
  { id: 'account', label: '个人账号', icon: CircleUserRound, adminOnly: false, group: '配置' },
]

export const NAVIGATION_GROUPS: NavigationGroup[] = ['监控', '配置']

export function visibleNavigation(isAdmin: boolean) {
  return NAVIGATION.filter((item) => isAdmin || !item.adminOnly)
}

/** Both roles start on services: it is the only section a viewer can ever see. */
function defaultSection(): SectionId {
  return 'services'
}

export function sectionLabel(id: SectionId): string {
  return NAVIGATION.find((item) => item.id === id)?.label ?? ''
}

/**
 * Resolves a raw hash segment to a section the current user may view. Unknown
 * values and admin-only sections requested by a viewer fall back to the default
 * section rather than rendering a blank page.
 */
export function resolveRoute(hash: string, isAdmin: boolean): AppRoute {
  const segments = hash.split('/').filter(Boolean)
  const match = NAVIGATION.find((item) => item.id === segments[0])
  if (!match || (match.adminOnly && !isAdmin)) return { section: defaultSection() }
  if (match.id === 'services' && segments.length === 2) {
    const serviceId = Number(segments[1])
    if (Number.isInteger(serviceId) && serviceId > 0) {
      return { section: 'services', serviceId }
    }
  }
  return { section: match.id }
}
