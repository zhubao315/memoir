import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { del, get, post, put } from '../../services/api'
import { Card, Empty, Field, Loading } from '../../components/ui'
import { useToast } from '../../components/Toast'

const MODES = [
  ['first_person', '第一人称'], ['third_person', '第三人称'], ['clean', '清理版'],
  ['transcript', '逐字稿'], ['literary', '文学版'], ['concise', '精简版'], ['documentary', '纪实版'],
]

export function StoryStudio() {
  const [params, setParams] = useSearchParams()
  const initial = params.get('tab')
  const [tab, setTab] = useState<'generate' | 'interview' | 'stories'>(
    initial === 'stories' || initial === 'interview' ? initial : 'generate'
  )
  const switchTab = (next: 'generate' | 'interview' | 'stories') => {
    setTab(next)
    const p = new URLSearchParams()
    if (next !== 'generate') p.set('tab', next)
    setParams(p, { replace: true })
  }
  useEffect(() => {
    if (initial === 'stories' || initial === 'interview') setTab(initial)
  }, [initial])
  const [memories, setMemories] = useState<any[]>([])
  const [memoryId, setMemoryId] = useState('')
  const [mode, setMode] = useState('first_person')
  const [title, setTitle] = useState('')
  const [story, setStory] = useState<any>(null)
  const [versions, setVersions] = useState<any[]>([])
  const [editContent, setEditContent] = useState('')
  const [prompts, setPrompts] = useState<any[]>([])
  const [topic, setTopic] = useState('childhood')
  const [interview, setInterview] = useState<any>(null)
  const [messages, setMessages] = useState<any[]>([])
  const [answer, setAnswer] = useState('')
  const toast = useToast()

  useEffect(() => {
    get('/v1/memories?limit=100').then((r: any) => { setMemories(r); if (r[0]) setMemoryId(r[0].id) }).catch(() => {})
    get('/v1/story/prompts?limit=5').then((r: any) => setPrompts(r)).catch(() => {})
  }, [])

  const generate = async () => {
    if (!memoryId) return toast.show('请先选择一段记忆作为素材', 'err')
    try {
      const s: any = await post('/v1/story/stories/generate', { mode, source_memory_id: memoryId, title: title || undefined })
      setStory(s)
      const v: any = await get(`/v1/story/stories/${s.id}/versions`)
      setVersions(v); setEditContent(v[v.length - 1]?.content || '')
      toast.show('故事已生成，原始记忆保持不变')
    } catch (e: any) { toast.show(e.message, 'err') }
  }

  const saveEdit = async () => {
    if (!story) return
    try {
      await post(`/v1/story/stories/${story.id}/versions`, { content: editContent, note: '人工编辑' })
      const v: any = await get(`/v1/story/stories/${story.id}/versions`)
      setVersions(v); toast.show('已保存为新版本，历史版本仍可恢复')
    } catch (e: any) { toast.show(e.message, 'err') }
  }

  const startInterview = async () => {
    try {
      const i: any = await post('/v1/story/interviews', { topic })
      setInterview(i)
      const m: any = await get(`/v1/story/interviews/${i.id}/messages`)
      setMessages(m)
    } catch (e: any) { toast.show(e.message, 'err') }
  }
  const sendAnswer = async () => {
    if (!interview || !answer.trim()) return
    try {
      const m: any = await post(`/v1/story/interviews/${interview.id}/answer`, { content: answer })
      setMessages(m); setAnswer('')
    } catch (e: any) { toast.show(e.message, 'err') }
  }

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 18 }}>
        <button className={`btn ${tab === 'generate' ? 'purple' : 'ghost'}`} onClick={() => switchTab('generate')}>✎ 故事生成</button>
        <button className={`btn ${tab === 'interview' ? 'purple' : 'ghost'}`} onClick={() => switchTab('interview')}>◈ AI 人生访谈</button>
        <button className={`btn ${tab === 'stories' ? 'purple' : 'ghost'}`} onClick={() => switchTab('stories')}>▤ 我的故事</button>
      </div>

      {tab === 'generate' && (
        <div className="grid grid-2">
          <Card title="从记忆生成故事">
            <Field label="选择原始记忆">
              <select className="select" value={memoryId} onChange={e => setMemoryId(e.target.value)}>
                {memories.length === 0 && <option value="">暂无记忆，请先去「我的记忆」添加</option>}
                {memories.map(m => <option key={m.id} value={m.id}>{m.title || m.raw_content?.slice(0, 20)}</option>)}
              </select>
            </Field>
            <Field label="叙事风格">
              <select className="select" value={mode} onChange={e => setMode(e.target.value)}>
                {MODES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </Field>
            <Field label="标题（可选）"><input className="input" value={title} onChange={e => setTitle(e.target.value)} placeholder="留空则自动生成" /></Field>
            <button className="btn purple" onClick={generate}>生成故事</button>
            <p style={{ fontSize: 12, color: '#5b6b85', marginTop: 12 }}>
              AI 只改善表达，不补充你没说过的日期、人物与地点；不确定的细节会列入「待确认」。原始记忆永不被覆盖。
            </p>
          </Card>
          <Card title="生成结果">
            {!story ? <Empty icon="✎" text="选择一段记忆，生成你的第一篇人生故事" /> : (
              <div>
                <div className="chip">{story.title}</div>
                <textarea className="textarea" style={{ minHeight: 220 }} value={editContent} onChange={e => setEditContent(e.target.value)} />
                <div style={{ marginTop: 10, display: 'flex', gap: 8 }}>
                  <button className="btn primary" onClick={saveEdit}>保存人工编辑版本</button>
                </div>
                <div style={{ marginTop: 16, fontSize: 13, color: '#5b6b85' }}>
                  版本数：{versions.length} · 每个 AI 版本都记录了模型、Prompt 版本与生成时间，可随时恢复。
                </div>
              </div>
            )}
          </Card>
        </div>
      )}

      {tab === 'interview' && (
        <div className="grid grid-2">
          <Card title="AI 人生访谈">
            {!interview ? (
              <div>
                <Field label="选择主题">
                  <select className="select" value={topic} onChange={e => setTopic(e.target.value)}>
                    <option value="childhood">童年记忆</option><option value="family_parents">家庭与父母</option>
                    <option value="love_marriage">爱情与婚姻</option><option value="career">职业与事业</option>
                    <option value="next_generation">给下一代的话</option>
                  </select>
                </Field>
                <Field label="今日推荐问题">
                  <div style={{ fontSize: 14, color: '#5b6b85' }}>{prompts[0]?.question || '加载中…'}</div>
                </Field>
                <button className="btn purple" onClick={startInterview}>开始访谈</button>
              </div>
            ) : (
              <div>
                <p style={{ fontSize: 13, color: '#5b6b85', marginBottom: 12 }}>访谈会依据你的回答动态追问；不想回答可以直接说“就这些”结束。</p>
                <div style={{ maxHeight: 380, overflowY: 'auto' }}>
                  {messages.map(m => <div key={m.id} className={`msg ${m.role === 'interviewee' ? 'me' : 'ai'}`}>{m.content}</div>)}
                </div>
                <div style={{ marginTop: 12 }}>
                  <textarea className="textarea" style={{ minHeight: 70 }} value={answer} onChange={e => setAnswer(e.target.value)} placeholder="在这里回答…" />
                  <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                    <button className="btn purple" onClick={sendAnswer}>回答</button>
                    <button className="btn ghost" onClick={async () => {
                      const m: any = await post(`/v1/story/interviews/${interview.id}/answer`, { content: '就这些吧', finish: true })
                      setMessages(m)
                    }}>结束访谈</button>
                  </div>
                </div>
              </div>
            )}
          </Card>
          <Card title="访谈如何进行">
            <ol style={{ paddingLeft: 20, lineHeight: 2 }}>
              <li>选择一个人生主题</li>
              <li>回答 AI 的问题（文字或语音）</li>
              <li>AI 理解你的回答，动态追问细节</li>
              <li>识别时间、人物、地点与情感</li>
              <li>确认结束后生成故事初稿</li>
              <li>你审核、编辑并保存</li>
            </ol>
            <p style={{ marginTop: 14, fontSize: 13, color: '#5b6b85' }}>
              不强迫回答敏感问题，不判断心理状态，不虚构你的经历。
            </p>
          </Card>
        </div>
      )}

      {tab === 'stories' && <StoriesList />}
    </div>
  )
}

function StoriesList() {
  const [stories, setStories] = useState<any[] | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [versions, setVersions] = useState<Record<string, any[]>>({})
  const [regenMode, setRegenMode] = useState<Record<string, string>>({})
  const [compare, setCompare] = useState<Record<string, [string | null, string | null]>>({})
  const toast = useToast()

  const load = () => get('/v1/story/stories').then((r: any) => setStories(r)).catch(() => setStories([]))
  useEffect(() => { load() }, [])

  const loadVersions = async (id: string) => {
    if (versions[id]) return
    const v: any = await get(`/v1/story/stories/${id}/versions`)
    setVersions((prev) => ({ ...prev, [id]: v }))
  }
  const toggle = (id: string) => {
    if (expanded === id) { setExpanded(null); return }
    setExpanded(id); loadVersions(id)
  }
  const regenerateStory = async (id: string) => {
    try {
      await post(`/v1/story/stories/${id}/regenerate`, { mode: regenMode[id] || 'first_person' })
      setVersions((prev) => ({ ...prev, [id]: [] }))
      toast.show('已生成新风格版本')
      load()
    } catch (e: any) { toast.show(e.message, 'err') }
  }
  const changeVisibility = async (id: string, visibility: string) => {
    try { await put(`/v1/story/stories/${id}/visibility`, { visibility }); toast.show('可见性已更新'); load() }
    catch (e: any) { toast.show(e.message, 'err') }
  }
  const removeStory = async (id: string) => {
    if (!confirm('删除故事？原始记忆与录音不会被删除。')) return
    try { await del(`/v1/story/stories/${id}`); toast.show('故事已删除'); load() }
    catch (e: any) { toast.show(e.message, 'err') }
  }

  if (!stories) return <Loading />
  return (
    <Card title={`我的故事 (${stories.length})`}>
      {stories.length === 0 ? <Empty icon="✎" text="还没有故事" /> : stories.map((s) => {
        const vs = versions[s.id] || []
        const sel = compare[s.id] || [null, null]
        const pick = (idx: number, val: string) => {
          const next: [string | null, string | null] = [...sel] as any
          next[idx] = val
          setCompare((p) => ({ ...p, [s.id]: next }))
        }
        return (
          <div className="story-manage" key={s.id}>
            <div className="story-manage-head">
              <div><b>{s.title || '无标题'}</b> <span className="chip">{s.status}</span> <span className="chip">{s.visibility === 'private' ? '仅自己' : s.visibility === 'family' ? '家庭可见' : '公开'}</span></div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <button className="btn sm ghost" onClick={() => toggle(s.id)}>版本 ({vs.length || '…'})</button>
                <button className="btn sm ghost" onClick={() => removeStory(s.id)}>删除</button>
              </div>
            </div>
            {expanded === s.id && (
              <div style={{ marginTop: 10 }}>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
                  <select className="select" style={{ width: 140 }} value={regenMode[s.id] || 'first_person'} onChange={(e) => setRegenMode((p) => ({ ...p, [s.id]: e.target.value }))}>
                    {MODES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                  <button className="btn sm purple" onClick={() => regenerateStory(s.id)}>重新生成该风格</button>
                  <select className="select" style={{ width: 110 }} value={s.visibility} onChange={(e) => changeVisibility(s.id, e.target.value)}>
                    <option value="private">仅自己</option><option value="family">家庭可见</option><option value="public">公开</option>
                  </select>
                </div>
                {vs.length === 0 ? <Loading text="加载版本…" /> : (
                  <>
                    <div style={{ fontSize: 12, color: '#5b6b85', marginBottom: 8 }}>
                      版本对比：
                      <select className="select" style={{ width: 150, display: 'inline-block', margin: '0 6px' }} value={sel[0] || ''} onChange={(e) => pick(0, e.target.value)}>
                        <option value="">版本 A</option>{vs.map((v) => <option key={v.id} value={v.id}>v{v.version_no} · {v.mode}</option>)}
                      </select>
                      <select className="select" style={{ width: 150, display: 'inline-block' }} value={sel[1] || ''} onChange={(e) => pick(1, e.target.value)}>
                        <option value="">版本 B</option>{vs.map((v) => <option key={v.id} value={v.id}>v{v.version_no} · {v.mode}</option>)}
                      </select>
                    </div>
                    {sel[0] || sel[1] ? (
                      <div className="version-compare">
                        {[0, 1].map((i) => {
                          const v = vs.find((x) => x.id === sel[i])
                          return <div key={i} className="version-pane"><b>{i === 0 ? '版本 A' : '版本 B'}</b><div className="version-text">{v ? v.content : '请选择版本'}</div></div>
                        })}
                      </div>
                    ) : (
                      <div className="version-list">
                        {vs.map((v) => <div key={v.id} className="version-item">
                          <span className="chip">v{v.version_no} · {v.mode}</span>
                          <span style={{ fontSize: 12, color: '#5b6b85' }}>{v.is_ai ? `${v.provider} / ${v.model}` : '人工编辑'} · {new Date(v.created_at).toLocaleString()}</span>
                          <div className="version-text">{v.content.slice(0, 200)}</div>
                        </div>)}
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        )
      })}
    </Card>
  )
}
