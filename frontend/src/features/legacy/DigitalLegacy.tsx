import { useEffect, useState } from 'react'
import { get, post } from '../../services/api'
import { Card, Empty, Field } from '../../components/ui'
import { useToast } from '../../components/Toast'

export function DigitalLegacy() {
  const [contacts, setContacts] = useState<any[]>([])
  const [policies, setPolicies] = useState<any[]>([])
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [toastMsg, setToastMsg] = useState('')
  const toast = useToast()
  const load = () => {
    get('/v1/legacy/contacts').then((r: any) => setContacts(r)).catch(() => {})
    get('/v1/legacy/policies').then((r: any) => setPolicies(r)).catch(() => {})
  }
  useEffect(load, [])

  const create = async () => {
    if (!name.trim()) return
    try { await post('/v1/legacy/contacts', { name, email: email || undefined }); setName(''); setEmail(''); load(); toast.show('联系人已添加') }
    catch (e: any) { toast.show(e.message, 'err') }
  }
  const act = async (id: string, action: string) => {
    try {
      const r: any = await post(`/v1/legacy/policies/${id}/${action}`)
      if (action === 'trigger-review') setToastMsg(r.message)
      load(); toast.show('操作成功')
    } catch (e: any) { toast.show(e.message, 'err') }
  }

  return (
    <div className="grid grid-2">
      <Card title="传承联系人">
        <Field label="姓名"><input className="input" value={name} onChange={e => setName(e.target.value)} /></Field>
        <Field label="邮箱（用于身份核验）"><input className="input" value={email} onChange={e => setEmail(e.target.value)} /></Field>
        <button className="btn primary" onClick={create}>添加联系人</button>
        <div style={{ marginTop: 16 }}>
          {contacts.length === 0 ? <Empty icon="✦" text="还没有传承联系人" /> : contacts.map(c => (
            <div className="timeline-item" key={c.id}><b>{c.name}</b><div className="date">{c.email || ''}</div></div>
          ))}
        </div>
      </Card>
      <Card title="访问策略与授权">
        <p style={{ color: '#5b6b85', fontSize: 13, marginBottom: 12 }}>
          传承联系人不会自动获得你的全部记忆。必须显式授权、设置生效条件、通过身份核验；可随时撤销，且有争议处理流程。
        </p>
        {contacts.length === 0 ? <Empty text="请先添加联系人" /> : (
          <button className="btn purple" onClick={async () => {
            try { await post('/v1/legacy/policies', { contact_id: contacts[0].id, trigger: 'manual' }); load(); toast.show('策略草稿已创建') }
            catch (e: any) { toast.show(e.message, 'err') }
          }}>为首位联系人创建策略草稿</button>
        )}
        <div style={{ marginTop: 16 }}>
          {policies.length === 0 ? <Empty text="还没有策略" /> : policies.map(p => (
            <div className="card" key={p.id} style={{ boxShadow: 'none', marginBottom: 10 }}>
              <b>策略状态：{p.status}</b> <span className="chip">授权：{p.granted ? '已授权' : '未授权'}</span>
              <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
                <button className="btn sm ghost" onClick={() => act(p.id, 'grant')}>授权</button>
                <button className="btn sm ghost" onClick={() => act(p.id, 'revoke')}>撤销</button>
                <button className="btn sm purple" onClick={() => act(p.id, 'trigger-review')}>发起交付审核</button>
              </div>
            </div>
          ))}
        </div>
        {toastMsg && <p style={{ marginTop: 12, fontSize: 13, color: '#2fae79' }}>{toastMsg}</p>}
      </Card>
    </div>
  )
}
