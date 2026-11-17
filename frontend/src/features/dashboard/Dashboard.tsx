import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { get } from '../../services/api'
import { Card, Empty, Loading, Stat } from '../../components/ui'

export function Dashboard() {
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')
  const nav = useNavigate()
  useEffect(() => {
    get('/v1/dashboard/summary').then(setData).catch(e => setError(e.message))
  }, [])

  if (error) return <Card><Empty icon="⚠" text={error} /></Card>
  if (!data) return <Loading />

  const c = data.counts
  return (
    <div>
      <div className="hero">
        <h2>早上好，欢迎回到 Memoir 👋</h2>
        <p>从一段记忆开始，慢慢写就你的人生之书。</p>
      </div>

      <div className="grid grid-4" style={{ marginTop: 18 }}>
        <Stat icon="▤" value={c.memories} label="记忆总数" />
        <Stat icon="✎" value={c.stories} label="人生故事" />
        <Stat icon="▧" value={c.photos} label="照片" />
        <Stat icon="◉" value={c.audios + c.videos} label="音视频" />
      </div>

      <div className="grid grid-2" style={{ marginTop: 18 }}>
        <Card title="今日记忆问题" extra={<button className="btn primary sm" onClick={() => nav('/story')}>开始回答 →</button>}>
          {data.daily_prompt
            ? <div style={{ fontSize: 17, lineHeight: 1.8 }}>“{data.daily_prompt.question}”</div>
            : <Empty text="问题库正在准备中" />}
        </Card>
        <Card title="人生里程碑">
          {data.milestones?.length
            ? <div className="timeline">{data.milestones.map((m: any) => (
                <div className="timeline-item" key={m.id}><div className="date">{m.occurred_at || ''}</div><b>{m.title}</b></div>
              ))}</div>
            : <Empty icon="✦" text="还没有标记重要时刻，去「我的记忆」添加里程碑吧" />}
        </Card>
      </div>

      <div className="grid grid-2" style={{ marginTop: 18 }}>
        <Card title="最近记忆" extra={<button className="btn ghost sm" onClick={() => nav('/memories')}>查看全部</button>}>
          {data.recent_memories?.length
            ? data.recent_memories.map((m: any) => (
                <div className="timeline-item" key={m.id}><div className="date">{m.occurred_at || ''}</div><b>{m.title || '无标题记忆'}</b></div>
              ))
            : <Empty text="还没有记忆，点击右上角开始记录" />}
        </Card>
        <Card title="最近故事" extra={<button className="btn ghost sm" onClick={() => nav('/story')}>进入工作室</button>}>
          {data.recent_stories?.length
            ? data.recent_stories.map((s: any) => (
                <div className="timeline-item" key={s.id}><b>{s.title || '无标题'}</b> <span className="chip">{s.status}</span></div>
              ))
            : <Empty icon="✎" text="用一段录音或一段文字，生成你的第一篇故事" />}
        </Card>
      </div>
    </div>
  )
}
