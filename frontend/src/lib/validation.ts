/**
 * Client-side form validation mirroring the backend's Pydantic bounds.
 *
 * The browser's own `required` / `minLength` validation is deliberately not used:
 * its bubble is drawn by the OS, cannot be styled to match the console, and
 * reports its own wording ("请将该文本增加为 8 个字符或更多"). Validating here
 * lets every message render through `Field`'s error slot instead.
 *
 * Bounds duplicated from `backend/app/schemas.py` are named constants so a
 * backend change has one place to land on this side.
 */

/** `UserCreate.username` */
export const USERNAME_MIN_LENGTH = 3
export const USERNAME_MAX_LENGTH = 64

/** `UserCreate.password` and `PasswordChangeInput.new_password` */
export const PASSWORD_MIN_LENGTH = 8
export const PASSWORD_MAX_LENGTH = 128

/** Validation messages keyed by form field name. */
export type FieldErrors<Field extends string> = Partial<Record<Field, string>>

/**
 * Checks a value that must be present and within a length range, returning the
 * first applicable message. `label` leads each message so it reads naturally
 * next to the field.
 */
export function checkLength(
  value: string,
  label: string,
  min: number,
  max: number,
): string | undefined {
  const trimmed = value.trim()
  if (!trimmed) return `请输入${label}。`
  if (trimmed.length < min) return `${label}至少需要 ${min} 个字符。`
  if (trimmed.length > max) return `${label}不能超过 ${max} 个字符。`
  return undefined
}

/** Passwords are checked untrimmed: leading and trailing spaces are significant. */
export function checkPassword(value: string, label: string): string | undefined {
  if (!value) return `请输入${label}。`
  if (value.length < PASSWORD_MIN_LENGTH) {
    return `${label}至少需要 ${PASSWORD_MIN_LENGTH} 个字符。`
  }
  if (value.length > PASSWORD_MAX_LENGTH) {
    return `${label}不能超过 ${PASSWORD_MAX_LENGTH} 个字符。`
  }
  return undefined
}

export type PasswordChangeField = 'currentPassword' | 'newPassword' | 'confirmPassword'

export function validatePasswordChange(values: {
  currentPassword: string
  newPassword: string
  confirmPassword: string
}): FieldErrors<PasswordChangeField> {
  const errors: FieldErrors<PasswordChangeField> = {}

  if (!values.currentPassword) errors.currentPassword = '请输入当前密码。'

  const newPasswordError = checkPassword(values.newPassword, '新密码')
  if (newPasswordError) {
    errors.newPassword = newPasswordError
  } else if (values.newPassword === values.currentPassword) {
    errors.newPassword = '新密码不能与当前密码相同。'
  }

  if (!values.confirmPassword) {
    errors.confirmPassword = '请再次输入新密码。'
  } else if (values.newPassword && values.newPassword !== values.confirmPassword) {
    errors.confirmPassword = '两次输入的新密码不一致。'
  }

  return errors
}

export type UserFormField = 'username' | 'password'

export function validateUserForm(values: {
  username: string
  password: string
}): FieldErrors<UserFormField> {
  const errors: FieldErrors<UserFormField> = {}

  const usernameError = checkLength(
    values.username,
    '用户名',
    USERNAME_MIN_LENGTH,
    USERNAME_MAX_LENGTH,
  )
  if (usernameError) errors.username = usernameError

  const passwordError = checkPassword(values.password, '密码')
  if (passwordError) errors.password = passwordError

  return errors
}

export type AlertFormField = 'name' | 'webhook_url'

export function validateAlertForm(
  values: { name: string; webhook_url: string },
  isNew: boolean,
): FieldErrors<AlertFormField> {
  const errors: FieldErrors<AlertFormField> = {}

  const nameError = checkLength(values.name, '告警名称', 1, 100)
  if (nameError) errors.name = nameError

  if (isNew && !values.webhook_url.trim()) {
    errors.webhook_url = '请输入 Webhook 地址。'
  } else if (values.webhook_url.trim()) {
    try {
      const url = new URL(values.webhook_url.trim())
      if (url.protocol !== 'https:' && url.protocol !== 'http:') {
        errors.webhook_url = '请输入有效的 HTTP/HTTPS 地址。'
      }
    } catch {
      errors.webhook_url = '请输入有效的 URL 地址。'
    }
  }

  return errors
}

export type HostFormField =
  | 'name'
  | 'hostname'
  | 'port'
  | 'username'
  | 'password'
  | 'private_key_path'
  | 'check_interval'

export function validateHostForm(
  values: {
    name: string
    hostname: string
    port: string
    username: string
    auth_type: string
    password: string
    private_key_path: string
    check_interval: string
    isAgent: boolean
    passwordRequired: boolean
  },
): FieldErrors<HostFormField> {
  const errors: FieldErrors<HostFormField> = {}

  const nameError = checkLength(values.name, '节点名称', 1, 100)
  if (nameError) errors.name = nameError

  if (!values.isAgent) {
    if (!values.hostname.trim()) errors.hostname = '请输入主机地址。'

    const port = Number(values.port)
    if (!values.port.trim() || !Number.isInteger(port) || port < 1 || port > 65535) {
      errors.port = '端口号必须是 1 到 65535 之间的整数。'
    }

    if (!values.username.trim()) errors.username = '请输入 SSH 用户名。'

    if (values.auth_type === 'password' && values.passwordRequired && !values.password) {
      errors.password = '请输入 SSH 密码。'
    }
    if (values.auth_type === 'key' && !values.private_key_path.trim()) {
      errors.private_key_path = '请输入私钥路径。'
    }
  }

  const interval = Number(values.check_interval)
  if (
    !values.check_interval.trim() ||
    !Number.isInteger(interval) ||
    interval < 60 ||
    interval > 86400
  ) {
    errors.check_interval = '探活间隔必须是 60 到 86400 之间的整数秒。'
  }

  return errors
}
