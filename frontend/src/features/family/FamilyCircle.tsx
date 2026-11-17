import { useEffect, useState } from 'react'
import { get, post } from '../../services/api'
import { Card, Empty, Field } from '../../components/ui'
import { useToast } from '../../components/Toast'

export function FamilyCircle() {
  const [families, setFamilies] = useState<any[]>([])
  const [name, setName] = useState('')
  const [active, setActive] = useState<string | null>(null)
  const [members, setMembers] = useState<any[]>([])
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState('collaborator')
  const [inviteResult, setInviteResult] = useState('')
  const toast = useToast()

  const load = () => get('/v1/family').then((r: any) => { setFamilies(r); if (r[0] && !active) setActive(r[0].id) })
  useEffect(() => { load() }, [])
  useEffect(() => {
    if (active) get(`/v1/family/${active}/members`).then((r: any) => setMembers(r)).catch(() => setMembers([]))
  }, [active])

  const create = async () => {
    if (!name.trim()) return
    try { await post('/v1/family', { name }); setName(''); load(); toast.show('家庭空间已创建') }
    catch (e: any) { toast.show(e.message, 'err') }
  }
  const invite = async () => {
    if (!active || !inviteEmail) return
    try {
      const r: any = await post(`/v1/family/${active}/invite`, { email: inviteEmail, role: inviteRole })
      setInviteResult(r.invite_url || r.token)
      toast.show('邀请已生成')
    } catch (e: any) { toast.show(e.message, 'err') }
  }

  return (
    <div className="grid grid-2">
      <Card title="创建家庭空间">
        <Field label="家庭名称"><input className="input" value={name} onChange={e => setName(e.target.value)} placeholder="例如：王氏家族" /></Field>
        <button className="btn primary" onClick={create}>创建空间</button>
        <div style={{ marginTop: 20 }}>
          <h4 style={{ marginBottom: 8 }}>我的家庭</h4>
          {families.length === 0 ? <Empty icon="♧" text="还没有家庭空间" /> : families.map(f => (
            <button key={f.id} className={`btn ${active === f.id ? 'primary' : 'ghost'}`} style={{ marginRight: 8, marginBottom: 8 }} onClick={() => setActive(f.id)}>{f.name}</button>
          ))}
        </div>
      </Card>
      <Card title="成员与邀请">
        {!active ? <Empty text="请先创建或选择一个家庭空间" /> : (
          <div>
            <h4 style={{ marginBottom: 8 }}>家庭成员 ({members.length})</h4>
            {members.map(m => <div key={m.id} className="timeline-item"><b>{m.display_name || m.user_id?.slice(0, 8)}</b> <span className="chip">{m.role}</span></div>)}
            <div style={{ marginTop: 14 }}>
              <Field label="邀请邮箱"><input className="input" value={inviteEmail} onChange={e => setInviteEmail(e.target.value)} placeholder="家人邮箱" /></Field>
              <Field label="角色">
                <select className="select" value={inviteRole} onChange={e => setInviteRole(e.target.value)}>
                  <option value="storyteller">讲述者</option><option value="collaborator">协作者</option>
                  <option value="viewer">只读成员</option><option value="admin">管理员</option>
                </select>
              </Field>
              <button className="btn primary" onClick={invite}>生成邀请</button>
              {inviteResult && <p style={{ marginTop: 10, fontSize: 13, wordBreak: 'break-all' }}>邀请链接：<code>{inviteResult}</code></p>}
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}
