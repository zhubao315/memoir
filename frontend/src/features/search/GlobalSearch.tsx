import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { get } from '../../services/api'
import { Card, Empty, Loading } from '../../components/ui'

const LABELS: Record<string, string> = { memory: '记忆', story: '故事', person: '人物', media: '媒体' }
const ICONS: Record<string, string> = { memory: '▤', story: '✎', person: '◇', media: '▧' }

export function GlobalSearch() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') || ''
  const [input, setInput] = useState(q)
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const nav = useNavigate()

  useEffect(() => { setInput(q) }, [q])
  useEffect(() => {
    if (!q) { setData(null); return }
    setLoading(true)
    get(`/v1/search?q=${encodeURIComponent(q)}`).then(setData).finally(() => setLoading(false))
  }, [q])

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    const next = new URLSearchParams()
    if (input.trim()) next.set('q', input.trim())
    setParams(next)
  }

  return (
    <Card title="全局搜索">
      <form onSubmit={submit} className="search-form">
        <input className="input" value={input} onChange={(e) => setInput(e.target.value)} placeholder="搜索记忆、故事、人物、媒体…" autoFocus />
        <button className="btn primary" type="submit">搜索</button>
      </form>
      {loading ? <Loading /> : !q ? <Empty icon="⌕" text="输入关键词搜索你授权的全部内容" /> : (
        <div style={{ marginTop: 16 }}>
          <div style={{ fontSize: 13, color: '#5b6b85', marginBottom: 10 }}>“{q}” 的结果：{data?.results?.length || 0} 条</div>
          {!data?.results?.length ? <Empty text="没有找到相关内容" /> : data.results.map((r: any, i: number) => (
            <div key={`${r.type}-${r.id}-${i}`} className="search-result" onClick={() => nav(r.href)}>
              <span className="search-ico">{ICONS[r.type] || '·'}</span>
              <div><b>{r.title}</b><div className="search-snippet">{r.snippet}</div></div>
              <span className="chip">{LABELS[r.type] || r.type}</span>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}
