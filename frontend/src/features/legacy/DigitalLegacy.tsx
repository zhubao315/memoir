import { useCallback, useEffect, useState } from 'react'
import { del, get, post } from '../../services/api'
import { Card, Empty, Field, Loading } from '../../components/ui'
import { useToast } from '../../components/Toast'

type Contact = {
  id: string; name: string; email?: string; phone?: string
  relationship?: string; identity_verified: number; verification_method?: string
}
type Policy = {
  id: string; contact_id: string; granted: boolean; status: string
  trigger: string; release_after_days?: number | null; share_scope: string[]
  granted_at?: string; revoked_at?: string; warning?: string
}
type LegacyEvent = {
  id: string; policy_id: string; event_type: string
  actor_id?: string; detail?: string; created_at: string
}

const STATUS_LABEL: Record<string, string> = {
  draft: '草稿', active: '已授权 · 待审核', disputed: '争议中',
  revoked: '已撤销', released: '已交付',
}
const EVENT_LABEL: Record<string, string> = {
  created: '创建策略', granted: '显式授权', revoked: '撤销授权',
  triggered: '发起人工审核', verified: '身份核验', disputed: '提出争议', released: '人工交付',
}

const S = {
  row: { display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' as const },
  contact: { paddingBottom: 14, borderBottom: '1px solid var(--line)', marginBottom: 12 },
  policy: {
    padding: 14, border: '1px solid var(--line)', borderRadius: 12,
    background: 'var(--surface-2)', marginBottom: 12,
  },
  muted: { fontSize: 12, color: 'var(--ink-soft)', marginTop: 4 },
  scope: { marginTop: 8 },
  actions: { display: 'flex', gap: 8, flexWrap: 'wrap' as const, marginTop: 10 },
  timeline: { maxHeight: 300, overflowY: 'auto' as const, marginTop: 8 },
  notice: {
    marginTop: 10, padding: 10, borderRadius: 8, background: '#eef3ff',
    color: 'var(--deep-blue)', fontSize: 13,
  },
  warn: { color: '#b26a00', fontSize: 12, marginTop: 6 },
  error: { color: 'var(--danger)', fontSize: 13, marginTop: 10 },
}

export function DigitalLegacy() {
  const [contacts, setContacts] = useState<Contact[]>([])
  const [policies, setPolicies] = useState<Policy[]>([])
  const [events, setEvents] = useState<LegacyEvent[]>([])
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [relationship, setRelationship] = useState('')
  const [policyContact, setPolicyContact] = useState('')
  const [trigger, setTrigger] = useState('manual')
  const [scopeText, setScopeText] = useState('')
  const [releaseDays, setReleaseDays] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const toast = useToast()

  const load = useCallback(() => {
    setError('')
    return Promise.all([
      get<Contact[]>('/v1/legacy/contacts'),
      get<Policy[]>('/v1/legacy/policies'),
      get<LegacyEvent[]>('/v1/legacy/events'),
    ]).then(([c, p, e]) => {
      setContacts(c); setPolicies(p); setEvents(e)
      setPolicyContact(prev => (prev && c.some(x => x.id === prev) ? prev : c[0]?.id || ''))
    }).catch((e: any) => setError(e.message || '加载传承数据失败'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const createContact = async () => {
    if (!name.trim()) return
    setBusy('contact')
    try {
      await post('/v1/legacy/contacts', {
        name: name.trim(), email: email.trim() || undefined,
        relationship: relationship.trim() || undefined,
      })
      setName(''); setEmail(''); setRelationship('')
      await load(); toast.show('联系人已添加')
    } catch (e: any) { toast.show(e.message, 'err') }
    finally { setBusy(null) }
  }

  const removeContact = async (c: Contact) => {
    if (!window.confirm(`确定删除联系人「${c.name}」吗？`)) return
    try {
      await del(`/v1/legacy/contacts/${c.id}`)
      await load(); toast.show('联系人已删除')
    } catch (e: any) { toast.show(e.message, 'err') }
  }

  const createPolicy = async () => {
    if (!policyContact) { toast.show('请先添加并选择联系人', 'err'); return }
    const scope = scopeText.split(/[,，\n]/).map(s => s.trim()).filter(Boolean)
    if (scope.some(s => !/^(story|memory):.+$/.test(s))) {
      toast.show('分享范围格式为 story:故事ID / memory:记忆ID，多个用逗号分隔', 'err')
      return
    }
    setBusy('policy')
    try {
      await post('/v1/legacy/policies', {
        contact_id: policyContact,
        trigger,
        share_scope: scope,
        release_after_days: releaseDays ? Number(releaseDays) : undefined,
      })
      setScopeText(''); setReleaseDays('')
      await load(); toast.show('策略草稿已创建（默认未授权，需显式授权）')
    } catch (e: any) { toast.show(e.message, 'err') }
    finally { setBusy(null) }
  }

  const act = async (p: Policy, action: 'grant' | 'revoke' | 'trigger-review') => {
    setBusy(p.id)
    setNotice('')
    try {
      const r: any = await post(`/v1/legacy/policies/${p.id}/${action}`)
      if (action === 'trigger-review') {
        setNotice(r.message || '已进入人工审核流程，需要身份核验与争议处理，不会自动交付数据')
      } else {
        setNotice(action === 'grant' ? '已显式授权，仍须通过人工审核才可能交付数据' : '授权已撤销，数据不会交付')
        if (r.warning) setNotice(r.warning)
      }
      await load()
      toast.show(action === 'grant' ? '授权成功' : action === 'revoke' ? '已撤销授权' : '已提交人工审核')
    } catch (e: any) { toast.show(e.message, 'err') }
    finally { setBusy(null) }
  }

  return (
    <div className="grid grid-2">
      <Card title="传承联系人">
        <Field label="姓名"><input className="input" value={name} onChange={e => setName(e.target.value)} placeholder="例如：女儿" /></Field>
        <Field label="邮箱（用于人工身份核验）"><input className="input" value={email} onChange={e => setEmail(e.target.value)} placeholder="name@example.com" /></Field>
        <Field label="关系"><input className="input" value={relationship} onChange={e => setRelationship(e.target.value)} placeholder="例如：长女" /></Field>
        <button className="btn primary" onClick={createContact} disabled={busy === 'contact' || !name.trim()}>添加联系人</button>

        <div style={{ marginTop: 16 }}>
          {loading ? <Loading text="加载联系人…" /> : contacts.length === 0 ? (
            <Empty icon="✦" text="还没有传承联系人" />
          ) : contacts.map(c => (
            <div key={c.id} style={S.contact}>
              <div style={S.row}>
                <b>{c.name}</b>
                <span className="chip">{c.relationship || '未填写关系'}</span>
                <span className="chip" style={{ background: c.identity_verified ? '#e6f8ef' : '#fff2e6', color: c.identity_verified ? '#1a8a5a' : '#b26a00' }}>
                  {c.identity_verified ? '身份已核验' : '未核验'}
                </span>
                <button className="btn danger sm" style={{ marginLeft: 'auto' }}
                  onClick={() => removeContact(c)}>删除</button>
              </div>
              <div style={S.muted}>{c.email || '未填写邮箱'}{c.verification_method ? ` · 核验方式：${c.verification_method}` : ''}</div>
            </div>
          ))}
        </div>

        <div className="section-title">新建访问策略</div>
        {contacts.length === 0 ? <Empty text="请先添加联系人" /> : (
          <>
            <Field label="选择联系人">
              <select className="select" value={policyContact} onChange={e => setPolicyContact(e.target.value)}>
                {contacts.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </Field>
            <Field label="触发方式">
              <select className="select" value={trigger} onChange={e => setTrigger(e.target.value)}>
                <option value="manual">手动触发（推荐）</option>
                <option value="scheduled">计划触发（仍需人工审核）</option>
              </select>
            </Field>
            <Field label="分享范围（必填，格式 story:ID / memory:ID，逗号分隔）">
              <input className="input" value={scopeText} onChange={e => setScopeText(e.target.value)}
                placeholder="story:xxx, memory:yyy" />
            </Field>
            <Field label="计划触发天数（可选，不会自动交付）">
              <input className="input" type="number" min={1} value={releaseDays}
                onChange={e => setReleaseDays(e.target.value)} placeholder="例如：30" />
            </Field>
            <button className="btn purple" onClick={createPolicy} disabled={busy === 'policy'}>创建策略草稿</button>
          </>
        )}
      </Card>

      <Card title="访问策略与授权">
        <p style={{ color: 'var(--ink-soft)', fontSize: 13, marginBottom: 12 }}>
          传承联系人不会自动获得你的全部记忆。必须显式授权、设置生效条件、通过身份核验；可随时撤销，且有争议处理流程。
          任何交付都需人工审核，系统不会自动交付数据。
        </p>
        {error && <p style={S.error}>{error}</p>}
        {loading ? <Loading text="加载策略…" /> : policies.length === 0 ? <Empty icon="✦" text="还没有策略" /> : policies.map(p => (
          <div key={p.id} style={S.policy}>
            <div style={S.row}>
              <b>策略状态</b>
              <span className="chip">{STATUS_LABEL[p.status] || p.status}</span>
              <span className="chip" style={{ background: p.granted ? '#e6f8ef' : '#fff2e6', color: p.granted ? '#1a8a5a' : '#b26a00' }}>
                {p.granted ? '已授权' : '未授权'}
              </span>
            </div>
            <div style={S.muted}>
              联系人：{contacts.find(c => c.id === p.contact_id)?.name || p.contact_id.slice(0, 8)}
              {' · '}触发：{p.trigger === 'scheduled' ? `计划（${p.release_after_days || '—'} 天）` : '手动'}
            </div>
            <div style={S.scope}>
              <span style={S.muted}>分享范围：</span>
              {p.share_scope?.length ? p.share_scope.map(s => <span className="chip" key={s}>{s}</span>)
                : <span className="chip">未配置（不交付任何内容）</span>}
            </div>
            {p.warning && <p style={S.warn}>⚠ {p.warning}</p>}
            <div style={S.actions}>
              <button className="btn sm ghost" onClick={() => act(p, 'grant')}
                disabled={!!busy || p.granted || p.status === 'revoked' || p.status === 'released'}>显式授权</button>
              <button className="btn sm ghost" onClick={() => act(p, 'revoke')}
                disabled={!!busy || p.status === 'revoked' || p.status === 'released'}>撤销授权</button>
              <button className="btn sm purple" onClick={() => act(p, 'trigger-review')}
                disabled={!!busy || !p.granted || p.status !== 'active'}>发起交付审核</button>
            </div>
          </div>
        ))}

        {notice && <div style={S.notice}>{notice}</div>}

        <div className="section-title">事件时间线</div>
        {events.length === 0 ? <Empty icon="◷" text="暂无事件记录" /> : (
          <div className="timeline" style={S.timeline}>
            {events.map(e => (
              <div key={e.id} className="timeline-item">
                <b>{EVENT_LABEL[e.event_type] || e.event_type}</b>
                <div className="date">{new Date(e.created_at).toLocaleString()}</div>
                {e.detail && <div style={S.muted}>{e.detail}</div>}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
