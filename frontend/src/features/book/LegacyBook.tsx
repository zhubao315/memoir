import { useCallback, useEffect, useState } from 'react'
import { del, get, getToken, post, put } from '../../services/api'
import { Card, Empty, Field, Loading } from '../../components/ui'
import { useToast } from '../../components/Toast'
import { useLightbox } from '../../components/Lightbox'

type Book = { id: string; title: string; status: string }
type Chapter = {
  id: string; title: string; content?: string; intro?: string
  order_index: number; story_ids?: string[]
}
type Story = { id: string; title?: string; visibility?: string }
type QR = {
  id: string; story_id?: string | null; token: string; url: string
  status: string; revoked_at?: string | null; created_at: string
}

const S = {
  row: { display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' as const },
  chapter: {
    display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' as const,
    padding: '10px 0', borderBottom: '1px solid var(--line)',
  },
  chapterTitle: { flex: 1, minWidth: 120 },
  actions: { display: 'inline-flex', gap: 4 },
  qrRow: {
    display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' as const,
    padding: '8px 0', borderBottom: '1px solid var(--line)',
  },
  code: { wordBreak: 'break-all' as const, fontSize: 12, display: 'block' as const, marginTop: 4 },
  muted: { fontSize: 12, color: 'var(--ink-soft)' },
  error: { color: 'var(--danger)', fontSize: 13, marginTop: 10 },
  flag: { background: 'var(--surface-2)', borderRadius: 6, padding: '2px 6px', fontSize: 11 },
}

export function LegacyBook() {
  const [books, setBooks] = useState<Book[]>([])
  const [title, setTitle] = useState('')
  const [author, setAuthor] = useState('')
  const [active, setActive] = useState<string | null>(null)
  const [detail, setDetail] = useState<any>(null)
  const [covers, setCovers] = useState<{ cover?: string; back?: string }>({})
  const [stories, setStories] = useState<Story[]>([])
  const [chapterTitle, setChapterTitle] = useState('')
  const [chapterStoryId, setChapterStoryId] = useState('')
  const [qrStoryId, setQrStoryId] = useState('')
  const [qrs, setQrs] = useState<QR[]>([])
  const [exporting, setExporting] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const lightbox = useLightbox()
  const toast = useToast()

  const loadBooks = useCallback(() => {
    setLoading(true); setError('')
    return get<Book[]>('/v1/book')
      .then(r => {
        setBooks(r)
        setActive(prev => (prev && r.some(b => b.id === prev) ? prev : r[0]?.id || null))
      })
      .catch((e: any) => setError(e.message || '加载回忆录失败'))
      .finally(() => setLoading(false))
  }, [])

  const loadDetail = useCallback((id: string) => {
    get<any>(`/v1/book/${id}`).then(setDetail).catch((e: any) => toast.show(e.message, 'err'))
  }, [toast])

  const loadQrs = useCallback((id: string) => {
    get<QR[]>(`/v1/book/${id}/qr`).then(setQrs).catch(() => setQrs([]))
  }, [])

  useEffect(() => { loadBooks() }, [loadBooks])
  useEffect(() => { get<Story[]>('/v1/story/stories').then(setStories).catch(() => setStories([])) }, [])
  useEffect(() => {
    if (!active) { setDetail(null); setQrs([]); return }
    loadDetail(active)
    loadQrs(active)
  }, [active, loadDetail, loadQrs])

  useEffect(() => {
    const book = detail?.book
    if (!book) { setCovers({}); return }
    const front = book.cover_media_id
    const back = book.settings?.back_cover_media_id
    Promise.all([
      front ? get<any>(`/v1/media/${front}/url`) : Promise.resolve(null),
      back ? get<any>(`/v1/media/${back}/url`) : Promise.resolve(null),
    ]).then(([f, b]: any) => setCovers({ cover: f?.url, back: b?.url })).catch(() => setCovers({}))
  }, [detail])

  const create = async () => {
    if (!title.trim()) return
    try {
      await post('/v1/book', { title: title.trim(), author: author.trim() || undefined })
      setTitle(''); setAuthor(''); await loadBooks(); toast.show('回忆录已创建')
    } catch (e: any) { toast.show(e.message, 'err') }
  }

  const addChapter = async () => {
    if (!active || !chapterTitle.trim()) return
    try {
      await post(`/v1/book/${active}/chapters`, {
        title: chapterTitle.trim(),
        order_index: detail?.chapters?.length || 0,
        story_ids: chapterStoryId ? [chapterStoryId] : [],
      })
      setChapterTitle(''); setChapterStoryId('')
      loadDetail(active); toast.show('章节已添加')
    } catch (e: any) { toast.show(e.message, 'err') }
  }

  const moveChapter = async (chapters: Chapter[], index: number, delta: number) => {
    if (!active) return
    const target = index + delta
    if (target < 0 || target >= chapters.length) return
    const cur = chapters[index], other = chapters[target]
    setDetail({ ...detail, chapters: chapters.map((c, i) =>
      i === index ? { ...c, order_index: other.order_index } : i === target ? { ...c, order_index: cur.order_index } : c,
    ).sort((a, b) => a.order_index - b.order_index) })
    try {
      // 通过现有 PUT 接口交换 order_index，实现上移/下移（部分更新不覆盖正文）。
      await put(`/v1/book/chapters/${cur.id}`, { order_index: other.order_index })
      await put(`/v1/book/chapters/${other.id}`, { order_index: cur.order_index })
      loadDetail(active)
    } catch (e: any) { toast.show(e.message, 'err'); loadDetail(active) }
  }

  const deleteChapter = async (id: string) => {
    if (!active || !window.confirm('确定删除该章节吗？')) return
    try {
      await del(`/v1/book/chapters/${id}`)
      loadDetail(active); toast.show('章节已删除')
    } catch (e: any) { toast.show(e.message, 'err') }
  }

  const makeQr = async () => {
    if (!active) return
    try {
      const r: any = await post(`/v1/book/${active}/qr${qrStoryId ? `?story_id=${qrStoryId}` : ''}`)
      setQrStoryId('')
      loadQrs(active)
      toast.show('二维码已生成（稳定令牌，可随时撤销）')
      return r
    } catch (e: any) { toast.show(e.message, 'err') }
  }

  const revokeQr = async (q: QR) => {
    if (!window.confirm('撤销后该公开链接立即失效，确定继续吗？')) return
    try {
      await post(`/v1/book/qr/${q.id}/revoke`)
      if (active) loadQrs(active)
      toast.show('二维码已撤销')
    } catch (e: any) { toast.show(e.message, 'err') }
  }

  const exportBook = async (format: string) => {
    if (!active || exporting) return
    setExporting(format)
    try {
      const res = await fetch(`/api/v1/book/${active}/export?format=${format}`, {
        headers: { Authorization: `Bearer ${getToken() || ''}` },
      })
      if (!res.ok) throw new Error((await res.json()).detail || '导出失败')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a'); a.href = url; a.download = `memoir.${format}`; a.click()
      URL.revokeObjectURL(url)
      toast.show(`${format.toUpperCase()} 导出完成`)
    } catch (e: any) { toast.show(e.message, 'err') }
    finally { setExporting(null) }
  }

  const chapters: Chapter[] = detail?.chapters || []
  const activeBook = books.find(b => b.id === active)
  const publicStories = stories.filter(s => s.visibility === 'public' || s.visibility === 'family')

  return (
    <div className="grid grid-2">
      <Card title="创建回忆录">
        <Field label="书名"><input className="input" value={title} onChange={e => setTitle(e.target.value)} placeholder="例如：我的人生" /></Field>
        <Field label="作者"><input className="input" value={author} onChange={e => setAuthor(e.target.value)} placeholder="你的名字" /></Field>
        <button className="btn primary" onClick={create} disabled={!title.trim()}>新建回忆录</button>
        <div style={{ marginTop: 18 }}>
          {loading ? <Loading text="正在加载回忆录…" /> : books.length === 0 ? (
            <Empty icon="▣" text="还没有回忆录，先创建一本吧" />
          ) : books.map(b => (
            <button key={b.id} className={`btn ${active === b.id ? 'primary' : 'ghost'}`}
              style={{ margin: '0 8px 8px 0' }} onClick={() => setActive(b.id)}>{b.title}</button>
          ))}
        </div>
      </Card>

      <Card title="章节 · 导出 · 公开故事"
        extra={activeBook ? <span className="chip">{activeBook.title}{activeBook.status === 'exported' ? ' · 已导出' : ''}</span> : undefined}>
        {error && <p style={S.error}>{error}</p>}
        {!active ? <Empty text="选择一本回忆录进行编辑" /> : !detail ? <Loading text="加载书籍详情…" /> : (
          <div>
            {(covers.cover || covers.back) && (
              <div>
                <div className="section-title">封面 / 封底预览</div>
                <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
                  {covers.cover && <button className="thumb" style={{ width: 110, height: 110 }}
                    onClick={() => lightbox.open(covers.cover!, '书籍封面', 'image')} title="点击预览封面">
                    <img src={covers.cover} alt="封面" />
                  </button>}
                  {covers.back && <button className="thumb" style={{ width: 110, height: 110 }}
                    onClick={() => lightbox.open(covers.back!, '书籍封底', 'image')} title="点击预览封底">
                    <img src={covers.back} alt="封底" />
                  </button>}
                </div>
              </div>
            )}

            <h4 style={{ marginBottom: 8 }}>章节 ({chapters.length})</h4>
            {chapters.length === 0 ? <Empty icon="▤" text="还没有章节" /> : (
              <div style={{ marginBottom: 12 }}>
                {chapters.map((c, i) => (
                  <div key={c.id} style={S.chapter}>
                    <span style={{ ...S.muted, width: 22 }}>{String(i + 1).padStart(2, '0')}</span>
                    <b style={S.chapterTitle}>{c.title}</b>
                    {!!c.story_ids?.length && <span style={S.flag}>绑定 {c.story_ids.length} 个故事</span>}
                    <span style={S.actions}>
                      <button className="btn ghost sm" onClick={() => moveChapter(chapters, i, -1)}
                        disabled={i === 0} title="上移">↑</button>
                      <button className="btn ghost sm" onClick={() => moveChapter(chapters, i, 1)}
                        disabled={i === chapters.length - 1} title="下移">↓</button>
                      <button className="btn danger sm" onClick={() => deleteChapter(c.id)} title="删除章节">删</button>
                    </span>
                  </div>
                ))}
              </div>
            )}
            <Field label="新增章节标题"><input className="input" value={chapterTitle} onChange={e => setChapterTitle(e.target.value)} /></Field>
            <Field label="绑定故事（可选，仅本人故事）">
              <select className="select" value={chapterStoryId} onChange={e => setChapterStoryId(e.target.value)}>
                <option value="">不绑定故事</option>
                {stories.map(s => <option key={s.id} value={s.id}>{s.title || '无标题'}</option>)}
              </select>
            </Field>
            <button className="btn ghost" onClick={addChapter} disabled={!chapterTitle.trim()}>添加章节</button>

            <div className="section-title">导出（PDF / Markdown / JSON）</div>
            <div style={{ ...S.row, marginBottom: 16 }}>
              <button className="btn primary sm" onClick={() => exportBook('pdf')} disabled={!!exporting}>
                {exporting === 'pdf' ? '导出中…' : '导出 PDF'}
              </button>
              <button className="btn ghost sm" onClick={() => exportBook('markdown')} disabled={!!exporting}>
                {exporting === 'markdown' ? '导出中…' : '导出 Markdown'}
              </button>
              <button className="btn ghost sm" onClick={() => exportBook('json')} disabled={!!exporting}>
                {exporting === 'json' ? '导出中…' : '导出 JSON'}
              </button>
              <span style={S.muted}>EPUB 即将支持</span>
            </div>

            <div className="section-title">公开故事二维码</div>
            <Field label="选择故事（私有故事不可生成公开链接）">
              <select className="select" value={qrStoryId} onChange={e => setQrStoryId(e.target.value)}>
                <option value="">不绑定故事（生成后不可匿名访问）</option>
                {publicStories.map(s => <option key={s.id} value={s.id}>{s.title || '无标题'} · {s.visibility === 'public' ? '公开' : '家庭可见'}</option>)}
              </select>
            </Field>
            <button className="btn purple sm" onClick={makeQr}>生成故事二维码</button>

            <div style={{ marginTop: 12 }}>
              <h4 style={{ marginBottom: 6 }}>二维码列表 ({qrs.length})</h4>
              {qrs.length === 0 ? <Empty icon="▣" text="暂无二维码" /> : qrs.map(q => (
                <div key={q.id} style={S.qrRow}>
                  <span className="chip">{q.status === 'active' ? '生效中' : '已撤销'}</span>
                  <code style={{ ...S.code, flex: 1 }}>{q.url}</code>
                  <span style={S.muted}>{new Date(q.created_at).toLocaleDateString()}</span>
                  {q.status === 'active' && (
                    <button className="btn danger sm" onClick={() => revokeQr(q)}>撤销</button>
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
