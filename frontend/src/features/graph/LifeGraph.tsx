import { useEffect, useState } from 'react'
import { get } from '../../services/api'
import { Card, Empty, Loading } from '../../components/ui'

export function LifeGraph() {
  const [data, setData] = useState<any>(null)
  useEffect(() => { get('/v1/dashboard/summary').then(setData).catch(() => setData({})) }, [])
  if (!data) return <Loading />
  return (
    <div className="grid grid-2">
      <Card title="人物关系网络">
        {data.milestones?.length ? (
          <div className="timeline">{data.milestones.map((m: any) => (
            <div className="timeline-item" key={m.id}><span className="chip">{m.occurred_at || '日期待确认'}</span> <b>{m.title}</b></div>
          ))}</div>
        ) : <Empty icon="◇" text="人物与事件关系会从记忆和访谈中逐步提取，形成你的人生图谱" />}
      </Card>
      <Card title="人生阶段">
        {data.life_stages?.length ? data.life_stages.map((s: any) => (
          <div className="timeline-item" key={s.id}><b>{s.name}</b><div className="date">{s.start_date || ''} — {s.end_date || ''}</div></div>
        )) : <Empty icon="⌁" text="还没有设置人生阶段。这是图谱与图谱问答的基础数据。" />}
      </Card>
    </div>
  )
}
