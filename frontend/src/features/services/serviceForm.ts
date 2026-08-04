import type { HealthRule, Probe, Service } from '../../types'
import { buildDefaultRule, syncRuleWithProbes, validateRule } from '../rules/healthRule'

/**
 * Editing shape of a probe. `headers` and `body` stay raw strings while the user
 * types so invalid JSON does not destroy their input mid-edit; they are parsed
 * once on submit.
 */
export type ProbeDraft = Omit<Probe, 'headers' | 'body'> & {
  headers: string
  body: string
}

export interface ServiceForm {
  host_id: string
  resource_group_id: string
  name: string
  probes: ProbeDraft[]
  health_rule: HealthRule
  start_command: string
  start_user: string
  check_interval: string
  enabled: boolean
  auto_restart: boolean
  alert_config_ids: number[]
}

/**
 * Validation messages keyed by form path. Probe fields use `probes.<index>.<field>`
 * so the editor can render the error inside the probe that caused it rather than
 * showing one vague message at the top of the dialog.
 */
export type FormErrors = Record<string, string>

export const PROBE_KEY_PATTERN = /^[a-zA-Z0-9_-]{1,64}$/

export function blankProbe(index: number): ProbeDraft {
  return {
    key: `probe-${index}`,
    name: `探活项 ${index}`,
    probe_type: 'get',
    process_pattern: '',
    url: '',
    headers: '{}',
    body: '{}',
    auth_type: 'none',
    auth_username: '',
    auth_secret: '',
    expected_status: 200,
    timeout_seconds: 10,
    enabled: true,
  }
}

export function blankServiceForm(): ServiceForm {
  const probe = blankProbe(1)
  return {
    host_id: '',
    resource_group_id: '',
    name: '',
    probes: [probe],
    health_rule: { probe: probe.key },
    start_command: '',
    start_user: '',
    check_interval: '60',
    enabled: true,
    auto_restart: false,
    alert_config_ids: [],
  }
}

/** Secrets are never returned by the API, so the field starts empty on edit. */
export function serviceToForm(service: Service): ServiceForm {
  return {
    host_id: String(service.host_id),
    resource_group_id: String(service.resource_group_id),
    name: service.name,
    probes: service.probes.map((probe) => ({
      ...probe,
      headers: JSON.stringify(probe.headers ?? {}, null, 2),
      body: JSON.stringify(probe.body ?? {}, null, 2),
      auth_secret: '',
    })),
    health_rule: service.health_rule,
    start_command: service.start_command ?? '',
    start_user: service.start_user ?? '',
    check_interval: String(service.check_interval),
    enabled: service.enabled,
    auto_restart: service.auto_restart,
    alert_config_ids: service.alert_configs.map((config) => config.id),
  }
}

interface ParsedJson<T> {
  value: T | null
  error: string | null
}

function parseJsonObject(raw: string): ParsedJson<Record<string, unknown>> {
  const trimmed = raw.trim()
  if (!trimmed) return { value: {}, error: null }
  try {
    const parsed: unknown = JSON.parse(trimmed)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return { value: null, error: '必须是 JSON 对象，例如 {"key": "value"}。' }
    }
    return { value: parsed as Record<string, unknown>, error: null }
  } catch {
    return { value: null, error: '不是有效的 JSON。' }
  }
}

function parseHeaders(raw: string): ParsedJson<Record<string, string>> {
  const { value, error } = parseJsonObject(raw)
  if (error || !value) return { value: null, error }
  const nonString = Object.entries(value).find(([, item]) => typeof item !== 'string')
  if (nonString) {
    return { value: null, error: `Header “${nonString[0]}” 的值必须是字符串。` }
  }
  return { value: value as Record<string, string>, error: null }
}

/**
 * Checks the form against the same rules the backend enforces in
 * `ServiceBase.validate_service` and `ServiceProbeInput.validate_probe`, so an
 * invalid submission is caught before the request.
 */
export function validateServiceForm(form: ServiceForm): FormErrors {
  const errors: FormErrors = {}

  if (!form.host_id) errors.host_id = '请选择所属节点。'
  if (!form.resource_group_id) errors.resource_group_id = '请选择资源组。'
  if (!form.name.trim()) errors.name = '请输入服务名称。'

  const interval = Number(form.check_interval)
  if (form.enabled && (!Number.isInteger(interval) || interval < 60 || interval > 86400)) {
    errors.check_interval = '探活间隔必须是 60 到 86400 之间的整数秒。'
  }

  if (form.auto_restart && !form.start_command.trim()) {
    errors.start_command = '开启掉线自动拉起时必须填写启动命令。'
  }

  const keyCounts = new Map<string, number>()
  for (const probe of form.probes) {
    const key = probe.key.trim()
    if (key) keyCounts.set(key, (keyCounts.get(key) ?? 0) + 1)
  }

  form.probes.forEach((probe, index) => {
    const at = (field: string) => `probes.${index}.${field}`
    const key = probe.key.trim()

    if (!key) errors[at('key')] = '请输入规则标识。'
    else if (!PROBE_KEY_PATTERN.test(key)) {
      errors[at('key')] = '规则标识只能包含字母、数字、下划线和短横线。'
    } else if ((keyCounts.get(key) ?? 0) > 1) {
      errors[at('key')] = '规则标识不能与其他探活项重复。'
    }

    if (!probe.name.trim()) errors[at('name')] = '请输入显示名称。'

    if (probe.probe_type === 'process') {
      if (!probe.process_pattern?.trim()) {
        errors[at('process_pattern')] = '进程探活必须填写匹配内容或 systemd 命令。'
      }
    } else {
      if (!probe.url?.trim()) errors[at('url')] = 'HTTP 探活必须填写请求 URL。'

      const headers = parseHeaders(probe.headers)
      if (headers.error) errors[at('headers')] = headers.error

      if (probe.probe_type === 'post') {
        const body = parseJsonObject(probe.body)
        if (body.error) errors[at('body')] = body.error
      }

      if (probe.auth_type === 'basic' && !probe.auth_username?.trim()) {
        errors[at('auth_username')] = 'Basic 认证必须填写用户名。'
      }
      // An existing probe keeps its stored secret when the field is left blank.
      if (probe.auth_type !== 'none' && !probe.auth_secret?.trim() && probe.id == null) {
        errors[at('auth_secret')] = '请输入认证密钥。'
      }
      if (probe.expected_status < 100 || probe.expected_status > 599) {
        errors[at('expected_status')] = '期望状态码必须在 100 到 599 之间。'
      }
    }

    if (probe.timeout_seconds < 1 || probe.timeout_seconds > 120) {
      errors[at('timeout_seconds')] = '超时必须在 1 到 120 秒之间。'
    }
  })

  if (!form.probes.some((probe) => probe.enabled)) {
    errors.probes = '至少需要启用一个探活项。'
  }

  const ruleError = validateRule(form.health_rule, form.probes)
  if (ruleError) errors.health_rule = ruleError

  return errors
}

interface ProbePayload {
  key: string
  name: string
  probe_type: Probe['probe_type']
  process_pattern: string | null
  url: string | null
  headers: Record<string, string>
  body: Record<string, unknown> | null
  auth_type: Probe['auth_type']
  auth_username: string | null
  auth_secret: string | null
  expected_status: number
  timeout_seconds: number
  enabled: boolean
}

export interface ServicePayload {
  host_id: number
  resource_group_id: number
  name: string
  probes: ProbePayload[]
  health_rule: HealthRule
  start_command: string | null
  start_user: string | null
  check_interval: number
  enabled: boolean
  auto_restart: boolean
  alert_config_ids: number[]
}

/**
 * Builds the request body. Call only after `validateServiceForm` returns no
 * errors: JSON fields are assumed parseable and fall back to empty on failure.
 *
 * A blank `auth_secret` on a saved probe is omitted so the backend keeps the
 * stored value rather than clearing it.
 */
export function buildServicePayload(form: ServiceForm): ServicePayload {
  return {
    host_id: Number(form.host_id),
    resource_group_id: Number(form.resource_group_id),
    name: form.name.trim(),
    probes: form.probes.map((probe) => {
      const isHttp = probe.probe_type !== 'process'
      const secret = probe.auth_secret?.trim()
      return {
        key: probe.key.trim(),
        name: probe.name.trim(),
        probe_type: probe.probe_type,
        process_pattern: probe.probe_type === 'process' ? probe.process_pattern?.trim() || null : null,
        url: isHttp ? probe.url?.trim() || null : null,
        headers: isHttp ? (parseHeaders(probe.headers).value ?? {}) : {},
        body: probe.probe_type === 'post' ? parseJsonObject(probe.body).value : null,
        auth_type: isHttp ? probe.auth_type : 'none',
        auth_username: isHttp && probe.auth_type === 'basic' ? probe.auth_username?.trim() || null : null,
        auth_secret: isHttp && probe.auth_type !== 'none' && secret ? secret : null,
        expected_status: Number(probe.expected_status),
        timeout_seconds: Number(probe.timeout_seconds),
        enabled: probe.enabled,
      }
    }),
    health_rule: syncRuleWithProbes(form.health_rule, form.probes),
    start_command: form.start_command.trim() || null,
    start_user: form.start_user.trim() || null,
    check_interval: Number(form.check_interval),
    enabled: form.enabled,
    auto_restart: form.auto_restart,
    alert_config_ids: form.alert_config_ids,
  }
}

/**
 * Applies a probe-list change and repairs the health rule, keeping the operators
 * the user built instead of resetting to a flat AND.
 */
export function withProbes(form: ServiceForm, probes: ProbeDraft[]): ServiceForm {
  const hasEnabled = probes.some((probe) => probe.enabled)
  return {
    ...form,
    probes,
    health_rule: hasEnabled ? syncRuleWithProbes(form.health_rule, probes) : buildDefaultRule(probes),
  }
}
