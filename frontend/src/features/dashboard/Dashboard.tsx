import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { get } from '../../services/api'
import { Card, Empty, Loading, Stat } from '../../components/ui'

function greeting() {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 11) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
}

const QUICK = [
  { ico: '✎', title: '快速记录', desc: '写下一刻的想法', to: '/memories', color: '#263841' },
  { ico: '◈', title: 'AI 人生访谈', desc: '让问题带你回忆', to: '/story?tab=interview', color: '#B77B50' },
  { ico: '◉', title: '说一段故事', desc: '录音自动转文字', to: '/voice', color: '#85958A' },
  { ico: '▧', title: '整理媒体库', desc: '照片与录音归档', to: '/media', color: '#B77B50' },
]

export function Dashboard() {
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')
  const nav = useNavigate()
  useEffect(() => { get('/v1/dashboard/summary').then(setData).catch((e) => setError(e.message)) }, [])

  if (error) return <Card><Empty icon="⚠" text={error} /></Card>
  if (!data) return <Loading />

  const c = data.counts
  const date = new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' })
  const activities = [
    ...(data.recent_memories || []).map((m: any) => ({ ...m, kind: '记忆', to: '/memories' })),
    ...(data.recent_stories || []).map((s: any) => ({ ...s, kind: '故事', to: '/story?tab=stories' })),
  ].slice(0, 8)
  const stages = data.life_stages || []

  return (
    <div>
      <div className="hero hero-dashboard">
        <div className="hero-inner">
          <div className="hero-date">{date}</div>
          <h2>{greeting()}，欢迎回到 Memoir 👋</h2>
          <p>从一段记忆开始，慢慢写就你的人生之书。</p>
          <div className="hero-progress">
            <span>人生阶段已记录 {stages.length} / 5</span>
            <div className="progress-track"><div className="progress-fill" style={{ width: `${Math.min(100, stages.length * 20)}%` }} /></div>
          </div>
        </div>
      </div>

      <div className="grid grid-4" style={{ marginTop: 18 }}>
        <Stat icon="▤" value={c.memories} label="记忆总数" onClick={() => nav('/memories')} />
        <Stat icon="✎" value={c.stories} label="人生故事" onClick={() => nav('/story?tab=stories')} />
        <Stat icon="▧" value={c.photos} label="照片" onClick={() => nav('/media?type=photo')} />
        <Stat icon="◉" value={c.audios + c.videos} label="音视频" onClick={() => nav('/media?type=audio,video')} />
      </div>

      <div className="section-title">快捷创作</div>
      <div className="grid grid-4">
        {QUICK.map((q) => (
          <button className="quick-card" key={q.title} onClick={() => nav(q.to)}>
            <span className="quick-ico" style={{ background: `${q.color}1f`, color: q.color }}>{q.ico}</span>
            <b>{q.title}</b>
            <span>{q.desc}</span>
            <span className="quick-arrow">→</span>
          </button>
        ))}
      </div>

      <div className="grid grid-2" style={{ marginTop: 18 }}>
        <div className="prompt-card">
          <div className="prompt-label">今日记忆问题 · AI 生成</div>
          <div className="prompt-question">{data.daily_prompt ? `“${data.daily_prompt.question}”` : '问题库正在准备中'}</div>
          <button className="btn purple sm" onClick={() => nav('/story?tab=interview')}>开始回答 →</button>
        </div>
        <Card title="人生里程碑" extra={<button className="btn ghost sm" onClick={() => nav('/graph')}>查看图谱</button>}>
          {data.milestones?.length ? (
            <div className="timeline">{data.milestones.map((m: any) => (
              <div className="timeline-item" key={m.id}><div className="date">{m.occurred_at || ''}</div><b>{m.title}</b></div>
            ))}</div>
          ) : <Empty icon="✦" text="还没有标记重要时刻" />}
        </Card>
      </div>

      <Card title="最近动态" extra={<button className="btn ghost sm" onClick={() => nav('/memories')}>查看全部</button>}>
        {activities.length === 0 ? <Empty text="还没有记录，写下第一段吧" /> : (
          <div className="timeline">
            {activities.map((a: any) => (
              <div className="timeline-item" key={`${a.kind}-${a.id}`} onClick={() => nav(a.to)} style={{ cursor: 'pointer' }}>
                <div className="date"><span className="chip">{a.kind}</span> {a.occurred_at || ''}</div>
                <b>{a.title || '无标题'}</b>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
