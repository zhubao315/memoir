const BASE = (import.meta.env.VITE_API_BASE as string | undefined) || '/api'

type Opts = RequestInit & { auth?: boolean }

export function getToken(): string | null {
  return localStorage.getItem('memoir_token')
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem('memoir_token', token)
  else localStorage.removeItem('memoir_token')
}

export function setUser(user: unknown | null) {
  if (user) localStorage.setItem('memoir_user', JSON.stringify(user))
  else localStorage.removeItem('memoir_user')
}

export function currentUser(): any {
  try { return JSON.parse(localStorage.getItem('memoir_user') || 'null') } catch { return null }
}

export async function api<T = any>(path: string, opts: Opts = {}): Promise<T> {
  const headers: Record<string, string> = { ...(opts.headers as Record<string, string> || {}) }
  const isForm = opts.body instanceof FormData
  if (!isForm && opts.body) headers['Content-Type'] = 'application/json'
  const token = getToken()
  if (token && opts.auth !== false) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${BASE}${path}`, { ...opts, headers })
  if (res.status === 401) {
    setToken(null); setUser(null)
    window.dispatchEvent(new Event('memoir:logout'))
  }
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error((data && data.detail) || `请求失败 (${res.status})`)
  return data as T
}

export const post = <T = any>(p: string, body?: unknown) =>
  api<T>(p, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })
export const put = <T = any>(p: string, body?: unknown) =>
  api<T>(p, { method: 'PUT', body: body === undefined ? undefined : JSON.stringify(body) })
export const del = <T = any>(p: string) => api<T>(p, { method: 'DELETE' })
export const get = <T = any>(p: string) => api<T>(p)
