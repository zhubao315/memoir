import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { get, post, setToken, setUser } from '../../services/api'
import { Card, Field } from '../../components/ui'
import { useToast } from '../../components/Toast'
import { ActivityLog } from './Activity'
import { ChunkUploader } from '../../components/ChunkUploader'

export function Settings() {
  const [oldPw, setOldPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [simple, setSimple] = useState(localStorage.getItem('memoir_simple') === 'true')
  const [sessions, setSessions] = useState<any[]>([])
  const nav = useNavigate()
  const toast = useToast()

  const changePw = async () => {
    if (!oldPw || newPw.length < 8) return toast.show('新密码至少 8 位', 'err')
    try {
      await post('/v1/auth/change-password', { old_password: oldPw, new_password: newPw })
      toast.show('密码已修改，请重新登录')
      setToken(null); setUser(null); nav('/login')
    } catch (e: any) { toast.show(e.message, 'err') }
  }

  const viewSessions = async () => {
    try { setSessions(await get('/v1/auth/sessions')) }
    catch (e: any) { toast.show(e.message, 'err') }
  }

  const toggleSimple = (v: boolean) => {
    setSimple(v)
    localStorage.setItem('memoir_simple', String(v))
    document.documentElement.dataset.simple = String(v)
    toast.show(v ? '已开启简洁模式' : '已恢复标准模式')
  }

  return (
    <div className="grid grid-2">
      <Card title="账户安全">
        <Field label="当前密码"><input className="input" type="password" value={oldPw} onChange={(e) => setOldPw(e.target.value)} /></Field>
        <Field label="新密码（至少 8 位）"><input className="input" type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} /></Field>
        <button className="btn primary" onClick={changePw}>修改密码</button>
        <div style={{ marginTop: 18, paddingTop: 14, borderTop: '1px solid var(--line)' }}>
          <button className="btn ghost sm" onClick={viewSessions}>查看有效会话</button>
          {sessions.length > 0 && (
            <div style={{ marginTop: 8 }}>
              {sessions.map((s) => <div key={s.id} className="chip">{s.id.slice(0, 8)} · {new Date(s.created_at).toLocaleString()}</div>)}
            </div>
          )}
        </div>
      </Card>
      <Card title="外观与体验">
        <div className="setting-row">
          <div><b>简洁模式</b><div className="setting-desc">大字号、大按钮，适合长辈使用</div></div>
          <button className={`btn ${simple ? 'primary' : 'ghost'}`} onClick={() => toggleSimple(!simple)}>{simple ? '已开启' : '关闭'}</button>
        </div>
        <div className="setting-row">
          <div><b>数据导出</b><div className="setting-desc">下载你的全部记忆、故事与媒体元数据</div></div>
          <a className="btn ghost" href="/api/v1/dashboard/export" onClick={(e) => {
            e.preventDefault()
            fetch('/api/v1/dashboard/export', { headers: { Authorization: `Bearer ${localStorage.getItem('memoir_token')}` } })
              .then((r) => r.blob()).then((b) => {
                const u = URL.createObjectURL(b); const a = document.createElement('a')
                a.href = u; a.download = 'memoir-export.json'; a.click(); URL.revokeObjectURL(u)
              })
          }}>导出</a>
        </div>
      </Card>
    </div>
  )
}

export function SettingsWithActivity() {
  const toast = useToast()
  return (
    <div>
      <Settings />
      <div style={{ marginTop: 18 }}>
        <Card title="大文件上传（分片 / 可恢复）">
          <ChunkUploader onUploaded={() => toast.show('文件已存入你的个人媒体库')} />
        </Card>
      </div>
      <div style={{ marginTop: 18 }}><ActivityLog /></div>
    </div>
  )
}
