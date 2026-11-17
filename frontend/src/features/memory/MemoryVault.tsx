import { useCallback, useEffect, useState } from 'react'
import { del, get, post, put } from '../../services/api'
import { Card, Empty, Field, Loading } from '../../components/ui'
import { useToast } from '../../components/Toast'
import { useLightbox } from '../../components/Lightbox'

const TYPES = [['memory', '记忆'], ['milestone', '里程碑'], ['daily', '日常'], ['travel', '旅行']]
const MOODS = [['happy', '😊 开心'], ['excited', '🤩 兴奋'], ['calm', '😌 平静'], ['sad', '😢 伤心'], ['angry', '😠 生气'], ['neutral', '😐 一般']]

function MemoryMedia({ memoryId }: { memoryId: string }) {
  const [items, setItems] = useState<any[]>([])
  const lightbox = useLightbox()
  useEffect(() => {
    get(`/v1/memories/${memoryId}/media`).then((r: any) => setItems(r)).catch(() => setItems([]))
  }, [memoryId])
  if (!items.length) return null
  return (
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
      {items.filter((x) => x.media_type === 'photo').map((x) => (
        <button key={x.id} className="thumb" onClick={() => lightbox.open(x.url, x.caption || '记忆配图')} title="点击预览大图">
          <img src={x.url} alt={x.caption || '记忆配图'} />
        </button>
      ))}
      {items.filter((x) => x.media_type !== 'photo').map((x) => (
        <button key={x.id} className="chip" onClick={() => lightbox.open(x.url, x.caption || '录音', x.media_type === 'video' ? 'video' : 'audio')} title={x.caption || '点击播放'}>
          {x.media_type === 'audio' ? '◉ 口述录音' : x.media_type === 'video' ? '▣ 视频' : '▤ 文档'}
          {x.caption ? ` · ${x.caption.slice(0, 12)}…` : ''}
        </button>
      ))}
    </div>
  )
}

export function MemoryVault() {
  const [items, setItems] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<string | null>(null)
  const [showTrash, setShowTrash] = useState(false)
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [moodFilter, setMoodFilter] = useState('')
  const [form, setForm] = useState<any>({ title: '', raw_content: '', occurred_at: '', memory_type: 'memory', mood: 'neutral', tags: '', location: '', visibility: 'private' })
  const toast = useToast()

  const load = useCallback(() => {
    setLoading(true)
    const q = new URLSearchParams({ limit: '100' })
    if (showTrash) q.set('show_trash', 'true')
    if (search) q.set('search', search)
    if (typeFilter) q.set('memory_type', typeFilter)
    if (moodFilter) q.set('mood', moodFilter)
    get(`/v1/memories?${q}`).then((r: any) => setItems(r)).catch((e: any) => toast.show(e.message, 'err')).finally(() => setLoading(false))
  }, [showTrash, search, typeFilter, moodFilter])

  useEffect(() => { load() }, [load])

  const setField = (k: string, v: any) => setForm((f: any) => ({ ...f, [k]: v }))

  const resetForm = () => {
    setEditing(null)
    setForm({ title: '', raw_content: '', occurred_at: new Date().toISOString().slice(0, 10), memory_type: 'memory', mood: 'neutral', tags: '', location: '', visibility: 'private' })
  }

  const save = async () => {
    if (!form.title.trim() && !form.raw_content.trim()) return toast.show('请填写标题或内容', 'err')
    const payload = {
      title: form.title,
      raw_content: form.raw_content,
      occurred_at: form.occurred_at || undefined,
      memory_type: form.memory_type,
      mood: form.mood,
      tags: form.tags.split(/[,，]/).map((t: string) => t.trim()).filter(Boolean),
      location: form.location ? { name: form.location } : {},
      visibility: form.visibility,
    }
    try {
      if (editing) await put(`/v1/memories/${editing}`, payload)
      else await post('/v1/memories', { ...payload, source: 'manual' })
      toast.show(editing ? '记忆已更新' : '记忆已保存')
      resetForm(); load()
    } catch (e: any) { toast.show(e.message, 'err') }
  }

  const edit = (m: any) => {
    setEditing(m.id)
    setForm({
      title: m.title || '', raw_content: m.raw_content || '', occurred_at: m.occurred_at || '',
      memory_type: m.memory_type || 'memory', mood: m.mood || 'neutral',
      tags: (m.tags || []).join(', '), location: m.location?.name || '', visibility: m.visibility || 'private',
    })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const remove = async (id: string) => {
    if (!confirm('确定移入回收站吗？原始内容仍可恢复。')) return
    await del(`/v1/memories/${id}`); toast.show('已移入回收站'); load()
  }
  const restore = async (id: string) => {
    await post(`/v1/memories/${id}/restore`); toast.show('已恢复到记忆库'); load()
  }
  const purge = async (id: string) => {
    if (!confirm('彻底删除后不可恢复，确定吗？')) return
    await del(`/v1/memories/${id}/purge`); toast.show('已彻底删除'); load()
  }

  return (
    <div>
      <Card title={editing ? '编辑记忆（原始文字可手动修订，AI 不会覆盖）' : '记录一段记忆'}>
        <div className="grid grid-2">
          <Field label="标题"><input className="input" value={form.title} onChange={(e) => setField('title', e.target.value)} placeholder="给这段记忆起个名字" /></Field>
          <Field label="发生日期"><input className="input" type="date" value={form.occurred_at || ''} onChange={(e) => setField('occurred_at', e.target.value)} /></Field>
        </div>
        <Field label="原始内容">
          <textarea className="textarea" value={form.raw_content} onChange={(e) => setField('raw_content', e.target.value)} placeholder="发生了什么？和谁在一起？你当时有什么感受？" />
        </Field>
        <div className="grid grid-3">
          <Field label="类型"><select className="select" value={form.memory_type} onChange={(e) => setField('memory_type', e.target.value)}>{TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></Field>
          <Field label="心情"><select className="select" value={form.mood} onChange={(e) => setField('mood', e.target.value)}>{MOODS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></Field>
          <Field label="可见范围"><select className="select" value={form.visibility} onChange={(e) => setField('visibility', e.target.value)}><option value="private">仅自己</option><option value="family">家庭可见</option><option value="public">公开</option></select></Field>
        </div>
        <div className="grid grid-2">
          <Field label="标签（逗号分隔）"><input className="input" value={form.tags} onChange={(e) => setField('tags', e.target.value)} placeholder="家人, 旅行, 童年" /></Field>
          <Field label="地点"><input className="input" value={form.location} onChange={(e) => setField('location', e.target.value)} placeholder="例如：北京什刹海" /></Field>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn primary" onClick={save}>{editing ? '保存修改' : '保存到记忆库'}</button>
          {editing && <button className="btn ghost" onClick={resetForm}>取消编辑</button>}
        </div>
      </Card>

      <div style={{ marginTop: 18 }}>
        <Card title={showTrash ? '回收站' : `全部记忆 (${items.length})`}
              extra={
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <input className="input" style={{ width: 150 }} value={search} onChange={(e) => setSearch(e.target.value)} placeholder="搜索记忆…" />
                  <select className="select" style={{ width: 110 }} value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
                    <option value="">全部类型</option>{TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                  <select className="select" style={{ width: 100 }} value={moodFilter} onChange={(e) => setMoodFilter(e.target.value)}>
                    <option value="">全部心情</option>{MOODS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                  <button className={`btn sm ${showTrash ? 'primary' : 'ghost'}`} onClick={() => setShowTrash(!showTrash)}>{showTrash ? '返回记忆库' : '回收站'}</button>
                </div>
              }
        >
          {loading ? <Loading /> : items.length === 0 ? (
            <Empty icon="▤" text={showTrash ? '回收站是空的' : '没有找到记忆，写下第一段吧'} />
          ) : (
            <div className="timeline">
              {items.map((m) => (
                <div className="timeline-item" key={m.id}>
                  <div className="date">{m.occurred_at || ''} · {m.memory_type}
                    {m.mood !== 'neutral' && <span className="chip">{m.mood}</span>}
                    {m.visibility !== 'private' && <span className="chip">{m.visibility === 'family' ? '家庭可见' : '公开'}</span>}
                  </div>
                  <b>{m.title || '无标题记忆'}</b>
                  <p style={{ color: '#5b6b85', fontSize: 14, margin: '4px 0' }}>{(m.raw_content || '').slice(0, 160)}</p>
                  {(m.tags || []).map((t: string) => <span className="chip" key={t}>{t}</span>)}
                  {m.location?.name && <span className="chip">📍 {m.location.name}</span>}
                  {!showTrash && <MemoryMedia memoryId={m.id} />}
                  <div style={{ marginTop: 6 }}>
                    {showTrash ? (
                      <>
                        <button className="btn sm ghost" onClick={() => restore(m.id)}>恢复</button>{' '}
                        <button className="btn sm danger" onClick={() => purge(m.id)}>彻底删除</button>
                      </>
                    ) : (
                      <>
                        <button className="btn sm ghost" onClick={() => edit(m)}>编辑</button>{' '}
                        <button className="btn sm ghost" onClick={() => remove(m.id)}>删除</button>
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
