import { useEffect, useState } from 'react'
import { get, post } from '../../services/api'
import { Card, Empty, Field } from '../../components/ui'
import { useToast } from '../../components/Toast'

export function LegacyBook() {
  const [books, setBooks] = useState<any[]>([])
  const [title, setTitle] = useState('')
  const [author, setAuthor] = useState('')
  const [active, setActive] = useState<string | null>(null)
  const [detail, setDetail] = useState<any>(null)
  const [covers, setCovers] = useState<{ cover?: string; back?: string }>({})
  const [chapterTitle, setChapterTitle] = useState('')
  const [qr, setQr] = useState('')
  const toast = useToast()

  const load = () => get('/v1/book').then((r: any) => { setBooks(r); if (r[0] && !active) setActive(r[0].id) })
  const loadDetail = (id: string) => get(`/v1/book/${id}`).then(setDetail)
  useEffect(() => { load() }, [])
  useEffect(() => { if (active) loadDetail(active) }, [active])
  useEffect(() => {
    const book = detail?.book
    if (!book) { setCovers({}); return }
    const front = book.cover_media_id
    const back = book.settings?.back_cover_media_id
    Promise.all([
      front ? get(`/v1/media/${front}/url`) : Promise.resolve(null),
      back ? get(`/v1/media/${back}/url`) : Promise.resolve(null),
    ]).then(([f, b]: any) => setCovers({ cover: f?.url, back: b?.url })).catch(() => setCovers({}))
  }, [detail])

  const create = async () => {
    if (!title.trim()) return
    try { await post('/v1/book', { title, author: author || undefined }); setTitle(''); setAuthor(''); load(); toast.show('回忆录已创建') }
    catch (e: any) { toast.show(e.message, 'err') }
  }
  const addChapter = async () => {
    if (!active || !chapterTitle.trim()) return
    try { await post(`/v1/book/${active}/chapters`, { title: chapterTitle, order_index: (detail?.chapters?.length || 0) }); setChapterTitle(''); loadDetail(active); toast.show('章节已添加') }
    catch (e: any) { toast.show(e.message, 'err') }
  }
  const makeQr = async () => {
    if (!active) return
    try { const r: any = await post(`/v1/book/${active}/qr`); setQr(r.url); toast.show('二维码已生成（稳定令牌，可撤销）') }
    catch (e: any) { toast.show(e.message, 'err') }
  }
  const exportBook = async (format: string) => {
    if (!active) return
    try {
      const res = await fetch(`/api/v1/book/${active}/export?format=${format}`, { headers: { Authorization: `Bearer ${localStorage.getItem('memoir_token')}` } })
      if (!res.ok) throw new Error((await res.json()).detail || '导出失败')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a'); a.href = url; a.download = `memoir.${format}`; a.click(); URL.revokeObjectURL(url)
      toast.show('导出完成')
    } catch (e: any) { toast.show(e.message, 'err') }
  }

  return (
    <div className="grid grid-2">
      <Card title="创建回忆录">
        <Field label="书名"><input className="input" value={title} onChange={e => setTitle(e.target.value)} placeholder="例如：我的人生" /></Field>
        <Field label="作者"><input className="input" value={author} onChange={e => setAuthor(e.target.value)} placeholder="你的名字" /></Field>
        <button className="btn primary" onClick={create}>新建回忆录</button>
        <div style={{ marginTop: 18 }}>
          {books.length === 0 ? <Empty icon="▣" text="还没有回忆录" /> : books.map(b => (
            <button key={b.id} className={`btn ${active === b.id ? 'primary' : 'ghost'}`} style={{ margin: '0 8px 8px 0' }} onClick={() => setActive(b.id)}>{b.title}</button>
          ))}
        </div>
      </Card>
      <Card title="章节与导出">
        {!detail ? <Empty text="选择一本回忆录进行编辑" /> : (
          <div>
            {(covers.cover || covers.back) && (
              <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
                {covers.cover && <a href={covers.cover} target="_blank" rel="noreferrer" title="封面">
                  <img src={covers.cover} alt="封面" style={{ width: 110, height: 110, objectFit: 'cover', borderRadius: 8, border: '1px solid #e4eaf3' }} />
                </a>}
                {covers.back && <a href={covers.back} target="_blank" rel="noreferrer" title="封底">
                  <img src={covers.back} alt="封底" style={{ width: 110, height: 110, objectFit: 'cover', borderRadius: 8, border: '1px solid #e4eaf3' }} />
                </a>}
              </div>
            )}
            <h4 style={{ marginBottom: 8 }}>章节 ({detail.chapters?.length || 0})</h4>
            {detail.chapters?.map((c: any) => <div className="timeline-item" key={c.id}><b>{c.title}</b></div>)}
            <Field label="新增章节标题"><input className="input" value={chapterTitle} onChange={e => setChapterTitle(e.target.value)} /></Field>
            <button className="btn ghost" onClick={addChapter}>添加章节</button>
            <div style={{ marginTop: 18, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button className="btn primary sm" onClick={() => exportBook('pdf')}>导出 PDF</button>
              <button className="btn ghost sm" onClick={() => exportBook('markdown')}>导出 Markdown</button>
              <button className="btn ghost sm" onClick={() => exportBook('json')}>导出 JSON</button>
              <button className="btn purple sm" onClick={makeQr}>生成故事二维码</button>
            </div>
            {qr && <p style={{ marginTop: 10, fontSize: 13 }}>公开故事页：<code>{qr}</code></p>}
          </div>
        )}
      </Card>
    </div>
  )
}
