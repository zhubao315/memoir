import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { post, setToken, setUser } from '../../services/api'
import { Field } from '../../components/ui'

export function Auth() {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const nav = useNavigate()

  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setError('')
    try {
      if (mode === 'register') {
        await post('/api/auth/register', { username, email, password })
      }
      const data: any = await post('/api/auth/login', { username, password })
      setToken(data.access_token); setUser(data.user)
      nav('/')
    } catch (err: any) { setError(err.message) }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <h1>Memoir</h1>
        <p className="tagline">Your Life. Your Stories. Your Legacy.</p>
        <form onSubmit={submit}>
          <Field label="用户名"><input className="input" value={username} onChange={e => setUsername(e.target.value)} required /></Field>
          {mode === 'register' && <Field label="邮箱"><input className="input" type="email" value={email} onChange={e => setEmail(e.target.value)} required /></Field>}
          <Field label="密码"><input className="input" type="password" value={password} onChange={e => setPassword(e.target.value)} required minLength={8} /></Field>
          {error && <p style={{ color: '#e05260', fontSize: 13, marginBottom: 10 }}>{error}</p>}
          <button className="btn primary" type="submit">{mode === 'login' ? '登录' : '注册并登录'}</button>
        </form>
        <div className="switch">
          {mode === 'login' ? '还没有账号？' : '已有账号？'}{' '}
          <a onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>{mode === 'login' ? '立即注册' : '返回登录'}</a>
        </div>
      </div>
    </div>
  )
}
