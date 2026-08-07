import { useState } from 'react'
import { KeyRound, ShieldCheck } from 'lucide-react'
import { api, errorMessage } from '../api'
import type { User } from '../types'
import {
  PASSWORD_MIN_LENGTH,
  validatePasswordChange,
  type FieldErrors,
  type PasswordChangeField,
} from '../lib/validation'
import { Button } from '../ui/Button'
import { PageHeader } from '../ui/Display'
import { TextField } from '../ui/Field'

const FORM_ID = 'password-change-form'

export function AccountPage({
  user,
  onPasswordChanged,
}: {
  user: User
  onPasswordChanged: () => void
}) {
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [fieldErrors, setFieldErrors] = useState<FieldErrors<PasswordChangeField>>({})

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setError('')
    const nextErrors = validatePasswordChange({
      currentPassword,
      newPassword,
      confirmPassword,
    })
    setFieldErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) return
    setBusy(true)
    try {
      await api.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      })
      onPasswordChanged()
    } catch (requestError) {
      setError(errorMessage(requestError))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHeader title="个人账号" description="管理当前登录身份和访问凭据。" />
      <div className="account-layout">
        <section className="account-identity">
          <span className="account-avatar">{user.username.slice(0, 1).toUpperCase()}</span>
          <div><span>当前账号</span><h2>{user.username}</h2><p>{user.is_admin ? '系统管理员' : '服务查看者'}</p></div>
          <ShieldCheck size={20} />
        </section>
        <section className="account-panel">
          <header><KeyRound size={19} /><div><h2>修改密码</h2><p>修改成功后需要使用新密码重新登录。</p></div></header>
          {/* noValidate: messages come from validatePasswordChange so they are
              styled with the rest of the console instead of the browser's bubble. */}
          <form id={FORM_ID} onSubmit={submit} className="account-form" noValidate>
            <TextField
              label="当前密码"
              type="password"
              autoComplete="current-password"
              value={currentPassword}
              error={fieldErrors.currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
            />
            <TextField
              label="新密码"
              type="password"
              autoComplete="new-password"
              value={newPassword}
              error={fieldErrors.newPassword}
              hint={`至少 ${PASSWORD_MIN_LENGTH} 个字符。`}
              onChange={(event) => setNewPassword(event.target.value)}
            />
            <TextField
              label="确认新密码"
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              error={fieldErrors.confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
            />
            {error && <div className="form-error" role="alert">{error}</div>}
            <Button type="submit" variant="primary" loading={busy}>更新密码</Button>
          </form>
        </section>
      </div>
    </>
  )
}
