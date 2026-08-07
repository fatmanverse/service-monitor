import { useState } from 'react'
import { ShieldCheck } from 'lucide-react'
import { api, clearToken, errorMessage, setToken } from '../api'
import { Button } from '../ui/Button'
import { TextField } from '../ui/Field'
import type { User } from '../types'

export function LoginPage({ onLogin }: { onLogin: (user: User) => void }) {
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      const token = await api.login(username, password)
      setToken(token.access_token)
      onLogin(await api.me())
    } catch (requestError) {
      clearToken()
      setError(errorMessage(requestError))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="login-page">
      <div className="login-main">
        <section className="login-panel">
          <div className="brand-mark">
            <ShieldCheck size={24} />
          </div>
          <h1>服务监控中心</h1>
          <p>统一管理节点、探活策略、故障拉起与服务告警。</p>
          <form className="login-form" onSubmit={submit} noValidate>
            <TextField
              label="用户名"
              value={username}
              autoComplete="username"
              onChange={(event) => setUsername(event.target.value)}
            />
            <TextField
              label="密码"
              type="password"
              value={password}
              autoComplete="current-password"
              onChange={(event) => setPassword(event.target.value)}
            />
            {error && (
              <div className="form-error" role="alert">
                {error}
              </div>
            )}
            <Button type="submit" variant="primary" loading={submitting}>
              进入控制台
            </Button>
          </form>
        </section>
      </div>
      <aside className="login-aside">
        <div className="login-aside-content">
          <strong>将故障发现和恢复动作放在同一个控制面。</strong>
          <p>并发执行进程、systemd 与 HTTP 探活，按嵌套在线规则判定服务状态，掉线后自动拉起并通知飞书。</p>
        </div>

      </aside>
    </main>
  )
}
