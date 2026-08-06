import type {
  Agent,
  AgentCommandStatus,
  AgentSecretRotation,
  AlertConfig,
  ApiErrorBody,
  Host,
  ProbeResult,
  ProbeLogPage,
  ResourceGroup,
  Service,
  User,
} from './types'

const TOKEN_KEY = 'service-monitor-token'

class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

/** True for requests cancelled by an AbortController; callers stay silent on these. */
export function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === 'AbortError'
}

export function errorMessage(error: unknown) {
  if (error instanceof Error) return error.message
  return '请求失败'
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

async function download(path: string, filename: string) {
  const token = getToken()
  const headers = new Headers()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(`/api${path}`, { headers })
  if (response.status === 401) {
    clearToken()
    onUnauthorized?.()
    throw new ApiError('登录状态已失效，请重新登录。', 401)
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorBody
    throw new ApiError(typeof body.detail === 'string' ? body.detail : '下载失败', response.status)
  }
  const url = URL.createObjectURL(await response.blob())
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

let onUnauthorized: (() => void) | null = null

/**
 * Registers the app-level reaction to an expired session. Any 401 on an
 * authenticated request clears the token and notifies this handler, so the
 * shell returns to the login screen instead of every page rendering its own
 * generic request error.
 */
export function setUnauthorizedHandler(handler: (() => void) | null) {
  onUnauthorized = handler
}

interface RequestOptions extends RequestInit {
  /** Login is the one endpoint where 401 means bad credentials, not expiry. */
  skipUnauthorizedHandler?: boolean
}

async function request<T>(path: string, init: RequestOptions = {}): Promise<T> {
  const { skipUnauthorizedHandler, ...requestInit } = init
  const token = getToken()
  const headers = new Headers(requestInit.headers)
  if (requestInit.body) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const response = await fetch(`/api${path}`, { ...requestInit, headers })

  if (response.status === 401 && !skipUnauthorizedHandler) {
    clearToken()
    onUnauthorized?.()
    throw new ApiError('登录状态已失效，请重新登录。', 401)
  }

  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorBody
    const detail = Array.isArray(body.detail)
      ? body.detail.map((item) => item.msg).join('；')
      : body.detail
    throw new ApiError(detail || `请求失败 (${response.status})`, response.status)
  }

  if (response.status === 204) return undefined as unknown as T
  return response.json() as Promise<T>
}

/** Forwarded to read-only endpoints so pollers can cancel requests in flight. */
interface ReadOptions {
  signal?: AbortSignal
}

export const api = {
  login: (username: string, password: string) =>
    request<{ access_token: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
      skipUnauthorizedHandler: true,
    }),
  me: (options: ReadOptions = {}) => request<User>('/auth/me', options),
  changePassword: (payload: object) =>
    request<void>('/auth/password', { method: 'PUT', body: JSON.stringify(payload) }),

  hosts: (options: ReadOptions = {}) => request<Host[]>('/hosts', options),
  createHost: (payload: object) =>
    request<Host>('/hosts', { method: 'POST', body: JSON.stringify(payload) }),
  updateHost: (id: number, payload: object) =>
    request<Host>(`/hosts/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteHost: (id: number) => request<void>(`/hosts/${id}`, { method: 'DELETE' }),
  probeHost: (id: number) => request<ProbeResult>(`/hosts/${id}/probe`, { method: 'POST' }),

  resourceGroups: (options: ReadOptions = {}) =>
    request<ResourceGroup[]>('/resource-groups', options),
  createResourceGroup: (payload: object) =>
    request<ResourceGroup>('/resource-groups', { method: 'POST', body: JSON.stringify(payload) }),
  updateResourceGroup: (id: number, payload: object) =>
    request<ResourceGroup>(`/resource-groups/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  deleteResourceGroup: (id: number) =>
    request<void>(`/resource-groups/${id}`, { method: 'DELETE' }),

  services: (options: ReadOptions = {}) => request<Service[]>('/services', options),
  service: (id: number, options: ReadOptions = {}) => request<Service>(`/services/${id}`, options),
  createService: (payload: object) =>
    request<Service>('/services', { method: 'POST', body: JSON.stringify(payload) }),
  updateService: (id: number, payload: object) =>
    request<Service>(`/services/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteService: (id: number) => request<void>(`/services/${id}`, { method: 'DELETE' }),
  probeService: (id: number) => request<ProbeResult>(`/services/${id}/probe`, { method: 'POST' }),
  restartService: (id: number) =>
    request<ProbeResult>(`/services/${id}/restart`, { method: 'POST' }),
  serviceLogs: (id: number, cursor?: string | null, options: ReadOptions = {}) => {
    const query = new URLSearchParams({ limit: '50' })
    if (cursor) query.set('cursor', cursor)
    return request<ProbeLogPage>(`/services/${id}/logs?${query}`, options)
  },

  agentCommand: (commandId: string, options: ReadOptions = {}) =>
    request<AgentCommandStatus>(`/agent-commands/${encodeURIComponent(commandId)}`, options),

  agents: (options: ReadOptions = {}) => request<Agent[]>('/agents', options),
  approveAgent: (id: number, payload: object) =>
    request<Agent>(`/agents/${id}/approve`, { method: 'POST', body: JSON.stringify(payload) }),
  rejectAgent: (id: number) => request<Agent>(`/agents/${id}/reject`, { method: 'POST' }),
  revokeAgent: (id: number) => request<Agent>(`/agents/${id}/revoke`, { method: 'POST' }),
  rotateAgentSecret: (id: number) =>
    request<AgentSecretRotation>(`/agents/${id}/rotate-secret`, { method: 'POST' }),
  downloadAgentCa: () => download('/agents/ca', 'service-monitor-ca.crt'),

  alerts: (options: ReadOptions = {}) => request<AlertConfig[]>('/alerts', options),
  createAlert: (payload: object) =>
    request<AlertConfig>('/alerts', { method: 'POST', body: JSON.stringify(payload) }),
  updateAlert: (id: number, payload: object) =>
    request<AlertConfig>(`/alerts/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteAlert: (id: number) => request<void>(`/alerts/${id}`, { method: 'DELETE' }),
  testAlert: (id: number) => request<ProbeResult>(`/alerts/${id}/test`, { method: 'POST' }),

  users: (options: ReadOptions = {}) => request<User[]>('/users', options),
  createUser: (payload: object) =>
    request<User>('/users', { method: 'POST', body: JSON.stringify(payload) }),
  deleteUser: (id: number) => request<void>(`/users/${id}`, { method: 'DELETE' }),
  userResourceGroups: (id: number, options: ReadOptions = {}) =>
    request<ResourceGroup[]>(`/users/${id}/resource-groups`, options),
  setUserResourceGroups: (id: number, groupIds: number[]) =>
    request<ResourceGroup[]>(`/users/${id}/resource-groups`, {
      method: 'PUT',
      body: JSON.stringify({ resource_group_ids: groupIds }),
    }),
  userServices: (id: number, options: ReadOptions = {}) =>
    request<Service[]>(`/users/${id}/services`, options),
  setUserServices: (id: number, serviceIds: number[]) =>
    request<Service[]>(`/users/${id}/services`, {
      method: 'PUT',
      body: JSON.stringify({ service_ids: serviceIds }),
    }),
}
