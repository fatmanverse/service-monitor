export type Status = 'unknown' | 'online' | 'offline'

export type ExecutionMode = 'ssh' | 'agent'

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
  port?: number | null
  username: string
  auth_type: 'password' | 'key' | 'agent'
  execution_mode: ExecutionMode
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
  start_user?: string | null
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

/**
 * Result of a probe / restart / alert-test action. Hosts running in `agent`
 * execution mode cannot answer synchronously: the backend queues a command and
 * replies with `mode: 'queued'` plus the `command_id` to poll.
 */
export interface ProbeResult {
  mode: 'immediate' | 'queued'
  success?: boolean | null
  status: Status
  message: string
  response_ms?: number | null
  restarted: boolean
  command_id?: string | null
  command_status?: string | null
}

/** Lifecycle of a queued agent command, as written by the backend. */
export type AgentCommandState = 'pending' | 'claimed' | 'succeeded' | 'failed' | 'expired'

/** Subset of the agent report that the backend stores in `result_json`. */
export interface AgentCommandReport {
  success: boolean
  message: string
  response_ms?: number | null
  restarted?: boolean
}

export interface AgentCommandStatus {
  command_id: string
  service_id: number
  command_type: string
  status: AgentCommandState
  result?: AgentCommandReport | null
  created_at: string
  claimed_at?: string | null
  finished_at?: string | null
  expires_at: string
}

export type AgentState = 'pending' | 'approved' | 'rejected' | 'revoked'

export interface Agent {
  id: number
  agent_uuid: string
  status: AgentState
  hostname: string
  runtime_user: string
  os_release: string
  architecture: string
  glibc_version: string
  agent_version: string
  last_seen_at?: string | null
  last_ip?: string | null
  config_revision: number
  created_at: string
  approved_at?: string | null
  revoked_at?: string | null
  host?: Host | null
  ssh_credentials_removed: boolean
}

export interface AgentSecretRotation {
  agent: Agent
  agent_secret: string
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
