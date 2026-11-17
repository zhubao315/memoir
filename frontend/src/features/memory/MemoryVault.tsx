import { useCallback, useEffect, useRef, useState } from 'react'
import { del, get, getToken, post, put } from '../../services/api'
import { Card, Empty, Field, Loading } from '../../components/ui'
import { useToast } from '../../components/Toast'
import { useLightbox } from '../../components/Lightbox'

const TYPES = [['memory', '记忆'], ['milestone', '里程碑'], ['daily', '日常'], ['travel', '旅行']]
const MOODS = [['happy', '😊 开心'], ['excited', '🤩 兴奋'], ['calm', '😌 平静'], ['sad', '😢 伤心'], ['angry', '😠 生气'], ['neutral', '😐 一般']]

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) || '/api'

type MediaItem = { id: string; media_type: string; caption: string | null; url: string }
type UploadTask = {
  key: string
  file: File
  name: string
  progress: number
  status: 'uploading' | 'done' | 'error'
  error?: string
}

/** 带进度上报的上传（api.ts 的 fetch 封装没有进度事件，这里单独用 XHR）。 */
function uploadFile(file: File, memoryId: string, onProgress: (p: number) => void): Promise<any> {
  return new Promise((resolve, reject) => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('memory_id', memoryId)
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${API_BASE}/v1/media/upload`)
    const token = getToken()
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100))
    }
    xhr.onload = () => {
      let data: any = {}
      try { data = JSON.parse(xhr.responseText) } catch { /* 非 JSON 响应 */ }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data)
      else reject(new Error((data && data.detail) || `上传失败 (${xhr.status})`))
    }
    xhr.onerror = () => reject(new Error('网络错误，上传失败'))
    xhr.send(fd)
  })
}

function MemoryMedia({ memoryId, onChange }: { memoryId: string; onChange?: () => void }) {
  const [items, setItems] = useState<MediaItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tasks, setTasks] = useState<UploadTask[]>([])
  const [dragging, setDragging] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)
  const lightbox = useLightbox()
  const toast = useToast()

  const reload = useCallback(() => {
    setLoading(true)
    setError('')
    get(`/v1/memories/${memoryId}/media`)
      .then((r: any) => setItems(r || []))
      .catch((e: any) => { setError(e.message || '媒体加载失败'); setItems([]) })
      .finally(() => setLoading(false))
  }, [memoryId])

  useEffect(() => { reload() }, [reload])

  const patchTask = (key: string, patch: Partial<UploadTask>) =>
    setTasks((prev) => prev.map((t) => (t.key === key ? { ...t, ...patch } : t)))

  const runTask = async (task: UploadTask) => {
    patchTask(task.key, { status: 'uploading', progress: 0, error: undefined })
    try {
      await uploadFile(task.file, memoryId, (p) => patchTask(task.key, { progress: p }))
      patchTask(task.key, { status: 'done', progress: 100 })
      reload()
      onChange?.()
    } catch (e: any) {
      patchTask(task.key, { status: 'error', error: e.message || '上传失败' })
    }
  }

  const enqueueFiles = (files: FileList | File[]) => {
    const picked = Array.from(files)
    if (!picked.length) return
    const fresh: UploadTask[] = picked.map((f, i) => ({
      key: `${Date.now()}-${i}-${f.name}`,
      file: f,
      name: f.name,
      progress: 0,
      status: 'uploading',
    }))
    setTasks((prev) => [...prev, ...fresh])
    fresh.forEach(runTask)
  }

  const preview = (x: MediaItem) => {
    if (x.media_type === 'document') {
      window.open(x.url, '_blank', 'noopener,noreferrer')
      return
    }
    const kind = x.media_type === 'video' ? 'video' : x.media_type === 'audio' ? 'audio' : 'image'
    lightbox.open(x.url, x.caption || '媒体预览', kind)
  }

  const remove = async (item: MediaItem) => {
    if (!confirm(`确定删除「${item.caption || '该媒体'}」吗？原始录音不可删除。`)) return
    try {
      await del(`/v1/media/${item.id}`)
      toast.show('已删除')
      reload()
      onChange?.()
    } catch (e: any) { toast.show(e.message, 'err') }
  }

  const active = tasks.filter((t) => t.status === 'uploading')

  return (
    <div style={{ marginTop: 10 }}>
      {/* 拖拽多文件上传区 */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); enqueueFiles(e.dataTransfer.files) }}
        onClick={() => fileInput.current?.click()}
        style={{
          border: `1px dashed ${dragging ? 'var(--electric-blue)' : 'var(--line)'}`,
          background: dragging ? 'var(--surface-2)' : 'transparent',
          borderRadius: 8, padding: '10px 12px', cursor: 'pointer',
          color: 'var(--ink-soft)', fontSize: 13, textAlign: 'center',
        }}
      >
        <input
          ref={fileInput} type="file" multiple hidden
          accept="image/*,video/*,audio/*,.pdf,.txt,.md"
          onChange={(e) => { if (e.target.files) enqueueFiles(e.target.files); e.target.value = '' }}
        />
        ＋ 拖拽或点击上传照片 / 音频 / 视频到这段记忆（支持多选）
      </div>

      {/* 上传进度与失败重试 */}
      {tasks.length > 0 && (
        <div style={{ marginTop: 8, display: 'grid', gap: 6 }}>
          {tasks.map((t) => (
            <div key={t.key} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
              <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={t.name}>{t.name}</span>
              <div style={{ width: 90, height: 5, background: 'var(--line)', borderRadius: 5, overflow: 'hidden' }}>
                <div style={{ width: `${t.progress}%`, height: '100%', background: t.status === 'error' ? 'var(--danger)' : 'var(--success)' }} />
              </div>
              <span style={{ width: 56, textAlign: 'right', color: t.status === 'error' ? 'var(--danger)' : 'var(--ink-soft)' }}>
                {t.status === 'uploading' ? `${t.progress}%` : t.status === 'done' ? '完成' : '失败'}
              </span>
              {t.status === 'error' && (
                <button className="btn sm ghost" onClick={() => runTask(t)} title={t.error || '重试'}>重试</button>
              )}
            </div>
          ))}
          {active.length > 0 && <span style={{ fontSize: 11, color: 'var(--ink-soft)' }}>正在上传 {active.length} 个文件…</span>}
        </div>
      )}

      {/* 附件列表：图片/音频/视频统一走 Lightbox 预览 */}
      {loading ? <Loading text="媒体加载中…" /> : error ? (
        <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 8 }}>
          {error} <button className="btn sm ghost" onClick={reload}>重试</button>
        </div>
      ) : items.length === 0 ? (
        <div style={{ fontSize: 12, color: 'var(--ink-soft)', marginTop: 8 }}>暂无附件，拖拽文件到上方即可添加。</div>
      ) : (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
          {items.map((x) => (
            <div key={x.id} style={{ position: 'relative' }}>
              {x.media_type === 'photo' ? (
                <button className="thumb" onClick={() => preview(x)} title={x.caption || '点击预览大图'}>
                  <img src={x.url} alt={x.caption || '记忆配图'} />
                </button>
              ) : (
                <button className="chip" onClick={() => preview(x)} title={x.caption || '点击播放/预览'}>
                  {x.media_type === 'audio' ? '◉ 口述录音' : x.media_type === 'video' ? '▣ 视频' : '▤ 文档'}
                  {x.caption ? ` · ${x.caption.slice(0, 12)}…` : ''}
                </button>
              )}
              {x.media_type !== 'audio' && (
                <button
                  className="btn sm ghost"
                  onClick={() => remove(x)}
                  title="删除媒体"
                  style={{ position: 'absolute', top: -6, right: -6, padding: '0 5px', fontSize: 11 }}
                >×</button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function MemoryVault() {
  const [items, setItems] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [listError, setListError] = useState('')
  const [editing, setEditing] = useState<string | null>(null)
  const [showTrash, setShowTrash] = useState(false)
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [moodFilter, setMoodFilter] = useState('')
  const [form, setForm] = useState<any>({ title: '', raw_content: '', occurred_at: '', memory_type: 'memory', mood: 'neutral', tags: '', location: '', visibility: 'private' })
  const toast = useToast()

  const load = useCallback(() => {
    setLoading(true)
    setListError('')
    const q = new URLSearchParams({ limit: '100' })
    if (showTrash) q.set('show_trash', 'true')
    if (search) q.set('search', search)
    if (typeFilter) q.set('memory_type', typeFilter)
    if (moodFilter) q.set('mood', moodFilter)
    get(`/v1/memories?${q}`)
      .then((r: any) => setItems(r))
      .catch((e: any) => { setListError(e.message || '记忆加载失败'); setItems([]) })
      .finally(() => setLoading(false))
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
    try { await del(`/v1/memories/${id}`); toast.show('已移入回收站'); load() }
    catch (e: any) { toast.show(e.message, 'err') }
  }
  const restore = async (id: string) => {
    try { await post(`/v1/memories/${id}/restore`); toast.show('已恢复到记忆库'); load() }
    catch (e: any) { toast.show(e.message, 'err') }
  }
  const purge = async (id: string) => {
    if (!confirm('彻底删除后不可恢复，确定吗？')) return
    try { await del(`/v1/memories/${id}/purge`); toast.show('已彻底删除'); load() }
    catch (e: any) { toast.show(e.message, 'err') }
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
          {loading ? <Loading /> : listError ? (
            <Empty icon="!" text={`${listError} `} />
          ) : items.length === 0 ? (
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
          {listError && <div style={{ textAlign: 'center', marginTop: 8 }}><button className="btn sm ghost" onClick={load}>重新加载</button></div>}
        </Card>
      </div>
    </div>
  )
}
