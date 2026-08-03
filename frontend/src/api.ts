import type { AlertConfig, ApiErrorBody, Host, ProbeResult, ResourceGroup, Service, User } from './types'

const TOKEN_KEY = 'service-monitor-token'

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message)
  }
}

export function errorMessage(error: unknown) {
  if (error instanceof ApiError || error instanceof Error) return error.message
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

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers = new Headers(init.headers)
  if (init.body) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(`/api${path}`, { ...init, headers })
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

export const api = {
  async login(username: string, password: string) {
    return request<{ access_token: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    })
  },
  me: () => request<User>('/auth/me'),
  hosts: () => request<Host[]>('/hosts'),
  createHost: (payload: object) =>
    request<Host>('/hosts', { method: 'POST', body: JSON.stringify(payload) }),
  deleteHost: (id: number) => request<void>(`/hosts/${id}`, { method: 'DELETE' }),
  probeHost: (id: number) => request<ProbeResult>(`/hosts/${id}/probe`, { method: 'POST' }),
  resourceGroups: () => request<ResourceGroup[]>('/resource-groups'),
  createResourceGroup: (payload: object) => request<ResourceGroup>('/resource-groups', { method: 'POST', body: JSON.stringify(payload) }),
  updateResourceGroup: (id: number, payload: object) => request<ResourceGroup>(`/resource-groups/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteResourceGroup: (id: number) => request<void>(`/resource-groups/${id}`, { method: 'DELETE' }),
  services: () => request<Service[]>('/services'),
  createService: (payload: object) =>
    request<Service>('/services', { method: 'POST', body: JSON.stringify(payload) }),
  updateService: (id: number, payload: object) =>
    request<Service>(`/services/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteService: (id: number) => request<void>(`/services/${id}`, { method: 'DELETE' }),
  probeService: (id: number) => request<ProbeResult>(`/services/${id}/probe`, { method: 'POST' }),
  restartService: (id: number) => request<ProbeResult>(`/services/${id}/restart`, { method: 'POST' }),
  alerts: () => request<AlertConfig[]>('/alerts'),
  createAlert: (payload: object) => request<AlertConfig>('/alerts', { method: 'POST', body: JSON.stringify(payload) }),
  updateAlert: (id: number, payload: object) => request<AlertConfig>(`/alerts/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteAlert: (id: number) => request<void>(`/alerts/${id}`, { method: 'DELETE' }),
  testAlert: (id: number) => request<ProbeResult>(`/alerts/${id}/test`, { method: 'POST' }),
  users: () => request<User[]>('/users'),
  createUser: (payload: object) =>
    request<User>('/users', { method: 'POST', body: JSON.stringify(payload) }),
  deleteUser: (id: number) => request<void>(`/users/${id}`, { method: 'DELETE' }),
  userResourceGroups: (id: number) => request<ResourceGroup[]>(`/users/${id}/resource-groups`),
  setUserResourceGroups: (id: number, groupIds: number[]) =>
    request<ResourceGroup[]>(`/users/${id}/resource-groups`, {
      method: 'PUT',
      body: JSON.stringify({ resource_group_ids: groupIds }),
    }),
}
