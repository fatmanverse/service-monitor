export type Status = 'unknown' | 'online' | 'offline'

export interface User {
  id: number
  username: string
  is_admin: boolean
  is_active: boolean
  created_at: string
}

export interface Host {
  id: number
  name: string
  hostname: string
  port: number
  username: string
  auth_type: 'password' | 'key'
  private_key_path?: string | null
  check_interval: number
  enabled: boolean
  alert_configs: AlertConfigReference[]
  status: Status
  last_checked_at?: string | null
  last_error?: string | null
  next_check_at: string
  created_at: string
}

export interface ResourceGroup {
  id: number
  name: string
  description?: string | null
  service_count: number
  user_count: number
  created_at: string
}

export interface Probe {
  id?: number
  key: string
  name: string
  probe_type: 'process' | 'get' | 'post'
  process_pattern?: string | null
  url?: string | null
  headers: Record<string, string>
  body?: Record<string, unknown> | null
  auth_type: 'none' | 'basic' | 'bearer'
  auth_username?: string | null
  auth_secret?: string | null
  expected_status: number
  timeout_seconds: number
  enabled: boolean
  last_success?: boolean | null
  last_checked_at?: string | null
  last_error?: string | null
  last_response_ms?: number | null
}

export type HealthRule =
  | { probe: string }
  | { op: 'AND' | 'OR'; children: HealthRule[] }

export interface Service {
  id: number
  host_id: number
  host_name: string
  resource_group_id: number
  resource_group_name: string
  name: string
  probes: Probe[]
  health_rule: HealthRule
  start_command?: string | null
  check_interval: number
  enabled: boolean
  auto_restart: boolean
  alert_configs: AlertConfigReference[]
  status: Status
  last_checked_at?: string | null
  last_error?: string | null
  last_response_ms?: number | null
  next_check_at: string
  created_at: string
}

export interface ProbeResult {
  success: boolean
  status: Status
  message: string
  response_ms?: number | null
  restarted: boolean
}

export interface AlertConfig {
  id: number
  name: string
  enabled: boolean
  webhook_configured: boolean
  service_count: number
  host_count: number
  created_at: string
  updated_at: string
}

export interface AlertConfigReference {
  id: number
  name: string
  enabled: boolean
}

export interface ApiErrorBody {
  detail?: string | Array<{ msg: string }>
}
