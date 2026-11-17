import { useEffect, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { currentUser, post, setToken, setUser } from '../services/api'

const NAV = [
  { to: '/', ico: '⌂', label: '首页 · Life Studio', group: '工作台' },
  { to: '/memories', ico: '▤', label: '我的记忆 · Memory Vault', group: '工作台' },
  { to: '/media', ico: '▧', label: '媒体库 · Media Gallery', group: '工作台' },
  { to: '/story', ico: '✎', label: 'AI 故事 · Story Studio', group: '创作' },
  { to: '/voice', ico: '◉', label: '语音录制 · Voice Studio', group: '创作' },
  { to: '/graph', ico: '◇', label: '人生图谱 · Life Graph', group: '创作' },
  { to: '/family', ico: '♧', label: '家庭空间 · Family Circle', group: '传承' },
  { to: '/book', ico: '▣', label: '回忆录 · Legacy Book', group: '传承' },
  { to: '/legacy', ico: '✦', label: '数字传承 · Digital Legacy', group: '传承' },
]

export function Layout({ children }: { children: ReactNode }) {
  const nav = useNavigate()
  const path = window.location.pathname
  const [simple, setSimple] = useState(localStorage.getItem('memoir_simple') === 'true')
  const [menuOpen, setMenuOpen] = useState(false)
  const user = currentUser()

  useEffect(() => {
    document.documentElement.dataset.simple = String(simple)
    localStorage.setItem('memoir_simple', String(simple))
  }, [simple])

  useEffect(() => {
    const onLogout = () => nav('/login')
    window.addEventListener('memoir:logout', onLogout)
    return () => window.removeEventListener('memoir:logout', onLogout)
  }, [nav])

  const logout = async () => {
    try { await post('/v1/auth/logout') } catch { /* ignore */ }
    setToken(null); setUser(null); nav('/login')
  }

  let lastGroup = ''
  return (
    <div className="app-shell">
      {menuOpen && <div className="nav-overlay" onClick={() => setMenuOpen(false)} />}
      <aside className={`sidebar${menuOpen ? ' open' : ''}`}>
        <div className="brand"><span className="brand-mark">M</span><span>Memoir</span></div>
        <nav className="nav">
          {NAV.map((item) => {
            const head = item.group !== lastGroup ? (lastGroup = item.group) : null
            return (
              <div key={item.to}>
                {head && <div className="nav-label">{head}</div>}
                <button className={`nav-item ${path === item.to || (item.to !== '/' && path.startsWith(item.to)) ? 'active' : ''}`} onClick={() => { nav(item.to); setMenuOpen(false) }}>
                  <span className="ico">{item.ico}</span><span>{item.label}</span>
                </button>
              </div>
            )
          })}
        </nav>
        <div className="sidebar-foot">Your Life. Your Stories. Your Legacy.<br />v1.0.0</div>
      </aside>
      <div className="main">
        <header className="topbar">
          <div className="topbar-left">
            <button className="menu-toggle" onClick={() => setMenuOpen(true)} aria-label="打开菜单">☰</button>
            <h1>{NAV.find((n) => n.to === path)?.label || 'Memoir'}</h1>
          </div>
          <div className="topbar-actions">
            <button className="btn primary sm" onClick={() => nav('/memories')}>＋ 快速记录</button>
            <button className="btn ghost sm" onClick={() => setSimple(!simple)} title="切换老年简洁模式">
              {simple ? 'Aa 标准' : 'Aa 简洁模式'}
            </button>
            <span className="user-chip" onClick={() => nav('/settings')} title="账户设置">{user?.username || ''} ⚙</span>
            <button className="btn ghost sm" onClick={logout}>退出</button>
          </div>
        </header>
        <main className="page">{children}</main>
      </div>
    </div>
  )
}
