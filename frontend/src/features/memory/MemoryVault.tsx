import { useEffect, useState } from 'react'
import { del, get, post, put } from '../../services/api'
import { Card, Empty, Field, Loading } from '../../components/ui'
import { useToast } from '../../components/Toast'

export function MemoryVault() {
  const [items, setItems] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10))
  const [editing, setEditing] = useState<string | null>(null)
  const toast = useToast()

  const load = () => {
    setLoading(true)
    get('/v1/memories?limit=100').then((r: any) => setItems(r)).finally(() => setLoading(false))
  }
  useEffect(load, [])

  const save = async () => {
    if (!title.trim() && !content.trim()) return toast.show('请填写标题或内容', 'err')
    try {
      if (editing) await put(`/v1/memories/${editing}`, { title, raw_content: content, occurred_at: date })
      else await post('/v1/memories', { title, raw_content: content, occurred_at: date, memory_type: 'memory' })
      toast.show(editing ? '记忆已更新' : '记忆已保存')
      setTitle(''); setContent(''); setEditing(null); load()
    } catch (e: any) { toast.show(e.message, 'err') }
  }

  const edit = (m: any) => { setEditing(m.id); setTitle(m.title || ''); setContent(m.raw_content || ''); setDate(m.occurred_at || date); window.scrollTo({ top: 0, behavior: 'smooth' }) }
  const remove = async (id: string) => {
    if (!confirm('确定移入回收站吗？原始内容仍可恢复。')) return
    await del(`/v1/memories/${id}`); toast.show('已移入回收站'); load()
  }

  return (
    <div>
      <Card title={editing ? '编辑记忆' : '记录一段记忆'}>
        <div className="grid grid-2">
          <Field label="标题"><input className="input" value={title} onChange={e => setTitle(e.target.value)} placeholder="给这段记忆起个名字" /></Field>
          <Field label="发生日期"><input className="input" type="date" value={date} onChange={e => setDate(e.target.value)} /></Field>
        </div>
        <Field label="原始内容（AI 不会覆盖这段文字）">
          <textarea className="textarea" value={content} onChange={e => setContent(e.target.value)} placeholder="发生了什么？和谁在一起？你当时有什么感受？" />
        </Field>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn primary" onClick={save}>{editing ? '保存修改' : '保存到记忆库'}</button>
          {editing && <button className="btn ghost" onClick={() => { setEditing(null); setTitle(''); setContent('') }}>取消编辑</button>}
        </div>
      </Card>

      <div style={{ marginTop: 18 }}>
      <Card title={`全部记忆 (${items.length})`}>
        {loading ? <Loading /> : items.length === 0
          ? <Empty icon="▤" text="记忆库还是空的，写下第一段吧" />
          : <div className="timeline">{items.map(m => (
              <div className="timeline-item" key={m.id}>
                <div className="date">{m.occurred_at || ''} · {m.memory_type}</div>
                <b>{m.title || '无标题记忆'}</b>
                <p style={{ color: '#5b6b85', fontSize: 14, margin: '4px 0' }}>{(m.raw_content || '').slice(0, 140)}</p>
                {(m.tags || []).map((t: string) => <span className="chip" key={t}>{t}</span>)}
                <div style={{ marginTop: 6 }}>
                  <button className="btn sm ghost" onClick={() => edit(m)}>编辑</button>{' '}
                  <button className="btn sm ghost" onClick={() => remove(m.id)}>删除</button>
                </div>
              </div>
            ))}</div>}
      </Card>
      </div>
    </div>
  )
}
