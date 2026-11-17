import { useEffect, useState } from 'react'
import { get } from '../../services/api'
import { Card, Empty, Loading } from '../../components/ui'

const LABELS: Record<string, string> = {
  register: '注册账号', login: '登录', logout: '退出', 'password.changed': '修改密码',
  'memory.update': '编辑记忆', 'memory.soft_delete': '移入回收站', 'memory.restore': '恢复记忆',
  'memory.purge': '彻底删除', 'legacy.grant': '授权数字传承', 'legacy.revoke': '撤销数字传承',
}

export function ActivityLog() {
  const [items, setItems] = useState<any[] | null>(null)
  useEffect(() => { get('/v1/activity?limit=80').then((r: any) => setItems(r)).catch(() => setItems([])) }, [])
  return (
    <Card title="活动与审计">
      <p style={{ fontSize: 12, color: '#5b6b85', marginBottom: 12 }}>仅显示你自己的关键操作记录，用于安全追溯。</p>
      {!items ? <Loading /> : items.length === 0 ? <Empty icon="◷" text="暂无活动记录" /> : (
        <div className="timeline">
          {items.map((a) => (
            <div className="timeline-item" key={a.id}>
              <div className="date">{new Date(a.created_at).toLocaleString()}</div>
              <b>{LABELS[a.action] || a.action}</b>
              {a.resource_type && <span className="chip">{a.resource_type}</span>}
              {a.detail && <div style={{ fontSize: 12, color: '#5b6b85' }}>{a.detail}</div>}
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}
