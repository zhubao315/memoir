import { useCallback, useEffect, useState, type CSSProperties } from 'react'
import { currentUser, del, get, post, put } from '../../services/api'
import { Card, Empty, Field, Loading } from '../../components/ui'
import { useToast } from '../../components/Toast'

type Family = { id: string; name: string; description?: string; owner_id: string }
type Member = { id: string; user_id: string; display_name?: string; role: string; joined_at?: string }
type Invitation = {
  id: string
  email: string
  role: string
  status: string
  expires_at: string
  invite_url?: string
  token: string
}

const ROLE_LABEL: Record<string, string> = {
  owner: '所有者',
  admin: '管理员',
  storyteller: '讲述者',
  collaborator: '协作者',
  viewer: '只读成员',
}

// 无法通过 global.css（不属于本模块）新增样式，统一用内联样式保持风格一致。
const S: Record<string, CSSProperties> = {
  flexWrap: { display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' },
  familyList: { display: 'grid', gap: 10 },
  familyCard: {
    display: 'flex', alignItems: 'center', gap: 12, width: '100%', textAlign: 'left',
    padding: '12px 14px', border: '1px solid var(--line)', borderRadius: 12,
    background: '#fff', cursor: 'pointer', font: 'inherit', transition: '.16s',
  },
  familyCardActive: { borderColor: 'var(--electric-blue)', background: '#f4f8ff' },
  avatar: {
    width: 38, height: 38, flex: '0 0 38px', borderRadius: 10,
    background: 'linear-gradient(135deg,#eaf1ff,#f3efff)', display: 'grid',
    placeItems: 'center', fontSize: 18, color: 'var(--memory-purple)',
  },
  familyBody: { display: 'flex', flexDirection: 'column', minWidth: 0, flex: 1 },
  small: { fontSize: 12, color: 'var(--ink-soft)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
  row: { display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' },
  actions: { marginLeft: 'auto', display: 'inline-flex', gap: 6 },
  selectSm: { width: 'auto', padding: '4px 8px', fontSize: 12 },
  inviteBox: {
    marginTop: 10, padding: 12, border: '1px dashed var(--line)',
    borderRadius: 10, background: 'var(--surface-2)',
  },
  code: { wordBreak: 'break-all', fontSize: 12, display: 'block', marginBottom: 8 },
  error: { color: 'var(--danger)', fontSize: 13, marginTop: 10 },
  date: { fontSize: 12, color: 'var(--ink-soft)', marginTop: 2 },
  inviteRow: { paddingBottom: 16 },
}

export function FamilyCircle() {
  const [families, setFamilies] = useState<Family[]>([])
  const [name, setName] = useState('')
  const [active, setActive] = useState<string | null>(null)
  const [members, setMembers] = useState<Member[]>([])
  const [invitations, setInvitations] = useState<Invitation[]>([])
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState('collaborator')
  const [inviteResult, setInviteResult] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const toast = useToast()
  const me = currentUser()

  const loadFamilies = useCallback(() => {
    setLoading(true)
    setError('')
    return get<Family[]>('/v1/family')
      .then((r) => {
        setFamilies(r)
        setActive((prev) => (prev && r.some((f) => f.id === prev) ? prev : r[0]?.id || null))
      })
      .catch((e: any) => setError(e.message || '加载家庭失败'))
      .finally(() => setLoading(false))
  }, [])

  const loadFamilyData = useCallback((id: string) => {
    get<Member[]>(`/v1/family/${id}/members`)
      .then(setMembers)
      .catch(() => setMembers([]))
    // 邀请列表仅 owner/admin 有权限；403 时静默留空。
    get<Invitation[]>(`/v1/family/${id}/invitations`)
      .then(setInvitations)
      .catch(() => setInvitations([]))
  }, [])

  useEffect(() => { loadFamilies() }, [loadFamilies])
  useEffect(() => { if (active) loadFamilyData(active) }, [active, loadFamilyData])

  const create = async () => {
    if (!name.trim()) return
    setBusy(true)
    try {
      await post('/v1/family', { name: name.trim() })
      setName('')
      await loadFamilies()
      toast.show('家庭空间已创建')
    } catch (e: any) { toast.show(e.message, 'err') }
    finally { setBusy(false) }
  }

  const invite = async () => {
    if (!active || !inviteEmail.trim()) return
    setBusy(true)
    try {
      const r: any = await post(`/v1/family/${active}/invite`, {
        email: inviteEmail.trim(), role: inviteRole,
      })
      setInviteResult(r.invite_url || r.token)
      setInviteEmail('')
      loadFamilyData(active)
      toast.show('邀请已生成，7 天内有效')
    } catch (e: any) { toast.show(e.message, 'err') }
    finally { setBusy(false) }
  }

  const copyInvite = async () => {
    if (!inviteResult) return
    const url = `${window.location.origin}/family/invite/${inviteResult.split('/').pop()}`
    try {
      await navigator.clipboard.writeText(url)
      toast.show('邀请链接已复制')
    } catch {
      toast.show('复制失败，请手动复制链接', 'err')
    }
  }

  const removeMember = async (m: Member) => {
    if (!active || !window.confirm(`确定移除成员「${m.display_name || m.user_id.slice(0, 8)}」吗？`)) return
    try {
      await del(`/v1/family/${active}/members/${m.id}`)
      loadFamilyData(active)
      toast.show('成员已移除')
    } catch (e: any) { toast.show(e.message, 'err') }
  }

  const changeRole = async (m: Member, role: string) => {
    if (!active) return
    try {
      await put(`/v1/family/${active}/members/${m.id}`, { role })
      loadFamilyData(active)
      toast.show('角色已更新')
    } catch (e: any) { toast.show(e.message, 'err') }
  }

  const revokeInvite = async (inv: Invitation) => {
    if (!active) return
    try {
      await post(`/v1/family/${active}/invitations/${inv.id}/revoke`)
      loadFamilyData(active)
      toast.show('邀请已撤销')
    } catch (e: any) { toast.show(e.message, 'err') }
  }

  const currentFamily = families.find((f) => f.id === active)
  const myRole = members.find(m => m.user_id === me?.id)?.role
  const isManager = myRole === 'owner' || myRole === 'admin'

  return (
    <div className="grid grid-2">
      <Card title="我的家庭空间">
        <Field label="家庭名称">
          <input className="input" value={name} onChange={e => setName(e.target.value)}
            placeholder="例如：王氏家族" disabled={busy} />
        </Field>
        <button className="btn primary" onClick={create} disabled={busy || !name.trim()}>创建空间</button>

        {error && <p style={S.error}>{error}</p>}
        <div style={{ marginTop: 20 }}>
          <h4 style={{ marginBottom: 8 }}>家庭列表 ({families.length})</h4>
          {loading ? <Loading text="正在加载家庭…" /> : families.length === 0 ? (
            <Empty icon="♧" text="还没有家庭空间，先创建一个吧" />
          ) : (
            <div style={S.familyList}>
              {families.map(f => (
                <button
                  key={f.id}
                  type="button"
                  style={{ ...S.familyCard, ...(active === f.id ? S.familyCardActive : {}) }}
                  onClick={() => { setActive(f.id); setInviteResult('') }}
                >
                  <span style={S.avatar}>♧</span>
                  <span style={S.familyBody}>
                    <b>{f.name}</b>
                    <small style={S.small}>{f.description || '点击管理成员与邀请'}</small>
                  </span>
                  {f.owner_id === me?.id && <span className="chip">我的空间</span>}
                </button>
              ))}
            </div>
          )}
        </div>
      </Card>

      <Card title="成员与邀请" extra={currentFamily ? <span className="chip">当前：{currentFamily.name}</span> : undefined}>
        {loading ? <Loading text="加载中…" /> : !active ? (
          <Empty text="请先创建或选择一个家庭空间" />
        ) : (
          <div>
            <h4 style={{ marginBottom: 8 }}>家庭成员 ({members.length})</h4>
            {members.length === 0 ? <Empty icon="♧" text="暂无成员" /> : (
              <div className="timeline">
                {members.map(m => (
                  <div key={m.id} className="timeline-item" style={S.row}>
                    <b>{m.display_name || m.user_id.slice(0, 8)}</b>
                    <span className={`chip role-${m.role}`}>{ROLE_LABEL[m.role] || m.role}</span>
                    {isManager && m.role !== 'owner' && m.user_id !== me?.id
                      && (myRole === 'owner' || m.role !== 'admin') && (
                      <span style={S.actions}>
                        {m.role !== 'admin' && (
                          <select
                            className="select"
                            style={S.selectSm}
                            value={m.role}
                            onChange={e => changeRole(m, e.target.value)}
                            aria-label="调整角色"
                          >
                            <option value="storyteller">讲述者</option>
                            <option value="collaborator">协作者</option>
                            <option value="viewer">只读成员</option>
                          </select>
                        )}
                        <button className="btn danger sm" onClick={() => removeMember(m)}>移除</button>
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}

            <div style={{ marginTop: 14 }}>
              <Field label="邀请邮箱">
                <input className="input" value={inviteEmail} onChange={e => setInviteEmail(e.target.value)}
                  placeholder="家人邮箱" disabled={busy} />
              </Field>
              <Field label="角色（邀请不授予所有者）">
                <select className="select" value={inviteRole} onChange={e => setInviteRole(e.target.value)}>
                  <option value="storyteller">讲述者</option>
                  <option value="collaborator">协作者</option>
                  <option value="viewer">只读成员</option>
                  <option value="admin">管理员</option>
                </select>
              </Field>
              <button className="btn primary" onClick={invite} disabled={busy || !inviteEmail.trim()}>生成邀请</button>
              {inviteResult && (
                <div style={S.inviteBox}>
                  <code style={S.code}>邀请链接（7 天内有效）：{inviteResult}</code>
                  <button className="btn ghost sm" onClick={copyInvite}>复制链接</button>
                </div>
              )}
            </div>

            <div style={{ marginTop: 16 }}>
              <h4 style={{ marginBottom: 8 }}>邀请记录</h4>
              {invitations.length === 0 ? <Empty icon="✉" text="暂无邀请记录" /> : invitations.map(inv => (
                <div key={inv.id} className="timeline-item" style={S.inviteRow}>
                  <div style={S.row}>
                    <b>{inv.email}</b>
                    <span className="chip">{ROLE_LABEL[inv.role] || inv.role}</span>
                    <span className="chip">{inv.status}</span>
                  </div>
                  <div style={S.date}>
                    过期时间：{inv.expires_at ? new Date(inv.expires_at).toLocaleString() : '—'}
                  </div>
                  {isManager && inv.status === 'pending' && (
                    <button className="btn danger sm" style={{ marginTop: 6 }}
                      onClick={() => revokeInvite(inv)}>撤销邀请</button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}
