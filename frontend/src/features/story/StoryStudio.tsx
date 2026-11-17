import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { del, get, post, put } from '../../services/api'
import { Card, Empty, Field, Loading } from '../../components/ui'
import { useToast } from '../../components/Toast'

// 叙事风格与后端 generate_story / StoryVersion.mode 保持一致
const MODES: [string, string][] = [
  ['first_person', '第一人称'], ['third_person', '第三人称'], ['clean', '清理版'],
  ['transcript', '逐字稿'], ['literary', '文学版'], ['concise', '精简版'], ['documentary', '纪实版'],
]
const modeLabel = (m: string) => MODES.find(([v]) => v === m)?.[1] || m

type Tab = 'generate' | 'interview' | 'stories'

interface Version {
  id: string
  story_id: string
  version_no: number
  mode: string
  content: string
  is_ai: boolean
  provider?: string | null
  model?: string | null
  prompt_version?: string | null
  needs_confirmation?: any[] | null
  note?: string | null
  created_at: string
}

// 当前版本（/stories/{id}/current 返回的版本对象）
const currentContent = (v: any): string => v?.content || ''
const fmtTime = (s?: string) => (s ? new Date(s).toLocaleString() : '')

export function StoryStudio() {
  const [params, setParams] = useSearchParams()
  const initial = params.get('tab')
  const [tab, setTab] = useState<Tab>(initial === 'stories' || initial === 'interview' ? initial : 'generate')
  const switchTab = (next: Tab) => {
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
  const [current, setCurrent] = useState<any>(null)
  const [versions, setVersions] = useState<Version[]>([])
  const [editContent, setEditContent] = useState('')
  const [generating, setGenerating] = useState(false)
  const [regenerating, setRegenerating] = useState('')
  const [loadingVersions, setLoadingVersions] = useState(false)
  const [prompts, setPrompts] = useState<any[]>([])
  const [topic, setTopic] = useState('childhood')
  const [interview, setInterview] = useState<any>(null)
  const [messages, setMessages] = useState<any[]>([])
  const [answer, setAnswer] = useState('')
  const [interviewBusy, setInterviewBusy] = useState(false)
  const toast = useToast()

  useEffect(() => {
    get('/v1/memories?limit=100').then((r: any) => { setMemories(r); if (r[0]) setMemoryId(r[0].id) }).catch(() => {})
    get('/v1/story/prompts?limit=5').then((r: any) => setPrompts(r)).catch(() => {})
  }, [])

  // 载入故事的版本列表与当前版本正文
  const refreshVersions = useCallback(async (storyId: string) => {
    setLoadingVersions(true)
    try {
      const [vs, cur]: [any, any] = await Promise.all([
        get(`/v1/story/stories/${storyId}/versions`),
        get(`/v1/story/stories/${storyId}/current`),
      ])
      setVersions(vs || [])
      setCurrent(cur)
      setEditContent(currentContent(cur))
    } catch (e: any) {
      toast.show(e.message, 'err')
    } finally {
      setLoadingVersions(false)
    }
  }, [toast])

  const generate = async () => {
    if (!memoryId) return toast.show('请先选择一段记忆作为素材', 'err')
    setGenerating(true)
    try {
      const s: any = await post('/v1/story/stories/generate', { mode, source_memory_id: memoryId, title: title || undefined })
      setStory(s)
      await refreshVersions(s.id)
      toast.show('故事已生成，原始记忆保持不变')
    } catch (e: any) { toast.show(e.message, 'err') }
    finally { setGenerating(false) }
  }

  // 一键切换风格重生成：基于同一素材生成新版本，不覆盖旧版
  const regenerate = async (nextMode: string) => {
    if (!story) return
    setRegenerating(nextMode)
    try {
      await post(`/v1/story/stories/${story.id}/regenerate`, { mode: nextMode })
      await refreshVersions(story.id)
      setMode(nextMode)
      toast.show(`已生成「${modeLabel(nextMode)}」新版本`)
    } catch (e: any) { toast.show(e.message, 'err') }
    finally { setRegenerating('') }
  }

  const saveEdit = async () => {
    if (!story) return
    try {
      await post(`/v1/story/stories/${story.id}/versions`, { content: editContent, note: '人工编辑' })
      await refreshVersions(story.id)
      toast.show('已保存为新版本，历史版本仍可恢复')
    } catch (e: any) { toast.show(e.message, 'err') }
  }

  const restore = async (versionId: string) => {
    if (!story) return
    try {
      await post(`/v1/story/stories/${story.id}/versions/${versionId}/restore`)
      await refreshVersions(story.id)
      toast.show('已恢复该版本（旧版本均保留）')
    } catch (e: any) { toast.show(e.message, 'err') }
  }

  const startInterview = async () => {
    setInterviewBusy(true)
    try {
      const i: any = await post('/v1/story/interviews', { topic })
      setInterview(i)
      const m: any = await get(`/v1/story/interviews/${i.id}/messages`)
      setMessages(m)
    } catch (e: any) { toast.show(e.message, 'err') }
    finally { setInterviewBusy(false) }
  }
  const sendAnswer = async (finish = false) => {
    if (!interview || (!answer.trim() && !finish)) return
    setInterviewBusy(true)
    try {
      const m: any = await post(`/v1/story/interviews/${interview.id}/answer`, { content: answer || '就这些吧', finish })
      setMessages(m); setAnswer('')
      if (finish) toast.show('访谈已结束，可到「故事生成」用逐字稿生成故事')
    } catch (e: any) { toast.show(e.message, 'err') }
    finally { setInterviewBusy(false) }
  }

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 18, flexWrap: 'wrap' }}>
        <button className={`btn ${tab === 'generate' ? 'purple' : 'ghost'}`} onClick={() => switchTab('generate')}>✎ 故事生成</button>
        <button className={`btn ${tab === 'interview' ? 'purple' : 'ghost'}`} onClick={() => switchTab('interview')}>◈ AI 人生访谈</button>
        <button className={`btn ${tab === 'stories' ? 'purple' : 'ghost'}`} onClick={() => switchTab('stories')}>▤ 我的故事</button>
      </div>

      {tab === 'generate' && (
        <div className="grid grid-2">
          <Card title="从记忆生成故事">
            {memories.length === 0 ? (
              <Empty icon="✎" text="暂无记忆，请先到「我的记忆」添加一段，再回来生成故事" />
            ) : (
              <>
                <Field label="选择原始记忆">
                  <select className="select" value={memoryId} onChange={e => setMemoryId(e.target.value)}>
                    {memories.map(m => <option key={m.id} value={m.id}>{m.title || m.raw_content?.slice(0, 20)}</option>)}
                  </select>
                </Field>
                <Field label="叙事风格">
                  <select className="select" value={mode} onChange={e => setMode(e.target.value)}>
                    {MODES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                </Field>
                <Field label="标题（可选）"><input className="input" value={title} onChange={e => setTitle(e.target.value)} placeholder="留空则自动生成" /></Field>
                <button className="btn purple" onClick={generate} disabled={generating || !memoryId}>
                  {generating ? '生成中…' : '生成故事'}
                </button>
                <p style={{ fontSize: 12, color: '#5b6b85', marginTop: 12 }}>
                  AI 只改善表达，不补充你没说过的日期、人物与地点；不确定的细节会列入「待确认」。原始记忆永不被覆盖。
                </p>
              </>
            )}
          </Card>
          <Card title="生成结果">
            {generating ? <Loading text="AI 正在撰写，请稍候…" /> : !story ? (
              <Empty icon="✎" text="选择一段记忆，生成你的第一篇人生故事" />
            ) : (
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
                  <div className="chip">{story.title}</div>
                  <span className="chip">当前 v{current?.version_no ?? versions.length} · {modeLabel(current?.mode || mode)}</span>
                </div>
                {/* 一键切换风格：点击即基于同一素材重新生成新版本 */}
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontSize: 12, color: '#5b6b85', marginBottom: 6 }}>一键切换叙事风格（生成新版本，不覆盖旧版）：</div>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {MODES.map(([v, l]) => (
                      <button
                        key={v}
                        className={`btn sm ${current?.mode === v ? 'purple' : 'ghost'}`}
                        onClick={() => regenerate(v)}
                        disabled={!!regenerating}
                      >
                        {regenerating === v ? '生成中…' : l}
                      </button>
                    ))}
                  </div>
                </div>
                {loadingVersions ? <Loading text="加载版本…" /> : (
                  <>
                    <textarea className="textarea" style={{ minHeight: 220 }} value={editContent} onChange={e => setEditContent(e.target.value)} />
                    <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      <button className="btn primary" onClick={saveEdit}>保存人工编辑版本</button>
                    </div>
                    {!!current?.needs_confirmation?.length && (
                      <div style={{ marginTop: 12, padding: 10, background: '#fff7ed', borderRadius: 8, fontSize: 12, color: '#9a3412' }}>
                        ⚠ 待确认细节：{current.needs_confirmation.join('、')}（请核对后再发布）
                      </div>
                    )}
                    {versions.length > 1 && (
                      <div style={{ marginTop: 16 }}>
                        <div style={{ fontSize: 13, color: '#5b6b85', marginBottom: 6 }}>历史版本（点击恢复）：</div>
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                          {versions.map(v => (
                            <button
                              key={v.id}
                              className={`btn sm ${v.id === current?.id ? 'primary' : 'ghost'}`}
                              onClick={() => restore(v.id)}
                              disabled={v.id === current?.id}
                              title={`v${v.version_no} · ${v.is_ai ? `${v.provider}/${v.model}` : '人工编辑'}`}
                            >
                              v{v.version_no} {v.is_ai ? 'AI' : '人工'}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                )}
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
                <button className="btn purple" onClick={startInterview} disabled={interviewBusy}>
                  {interviewBusy ? '开始中…' : '开始访谈'}
                </button>
              </div>
            ) : (
              <div>
                <p style={{ fontSize: 13, color: '#5b6b85', marginBottom: 12 }}>访谈会依据你的回答动态追问；不想回答可以直接说“就这些”结束。</p>
                <div style={{ maxHeight: 380, overflowY: 'auto' }}>
                  {messages.map(m => <div key={m.id} className={`msg ${m.role === 'interviewee' ? 'me' : 'ai'}`}>{m.content}</div>)}
                </div>
                <div style={{ marginTop: 12 }}>
                  <textarea className="textarea" style={{ minHeight: 70 }} value={answer} onChange={e => setAnswer(e.target.value)} placeholder="在这里回答…" />
                  <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
                    <button className="btn purple" onClick={() => sendAnswer(false)} disabled={interviewBusy || !answer.trim()}>
                      {interviewBusy ? '发送中…' : '回答'}
                    </button>
                    <button className="btn ghost" onClick={() => sendAnswer(true)} disabled={interviewBusy}>结束访谈</button>
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

      {tab === 'stories' && <StoriesList onOpenInStudio={(s) => { setStory(s); switchTab('generate'); refreshVersions(s.id) }} />}
    </div>
  )
}

function StoriesList({ onOpenInStudio }: { onOpenInStudio: (s: any) => void }) {
  const [stories, setStories] = useState<any[] | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [versions, setVersions] = useState<Record<string, Version[]>>({})
  const [regenMode, setRegenMode] = useState<Record<string, string>>({})
  const [compare, setCompare] = useState<Record<string, [string | null, string | null]>>({})
  const [busyId, setBusyId] = useState('')
  const toast = useToast()

  const load = () => get('/v1/story/stories').then((r: any) => setStories(r)).catch(() => setStories([]))
  useEffect(() => { load() }, [])

  const loadVersions = async (id: string) => {
    if (versions[id]) return
    try {
      const v: any = await get(`/v1/story/stories/${id}/versions`)
      setVersions((prev) => ({ ...prev, [id]: v }))
    } catch (e: any) { toast.show(e.message, 'err') }
  }
  const toggle = (id: string) => {
    if (expanded === id) { setExpanded(null); return }
    setExpanded(id); loadVersions(id)
  }

  const regenerateStory = async (id: string) => {
    setBusyId(id)
    try {
      await post(`/v1/story/stories/${id}/regenerate`, { mode: regenMode[id] || 'first_person' })
      setVersions((prev) => ({ ...prev, [id]: [] }))
      toast.show('已生成新风格版本')
      load(); await loadVersions(id)
    } catch (e: any) { toast.show(e.message, 'err') }
    finally { setBusyId('') }
  }
  const restoreVersion = async (id: string, versionId: string) => {
    setBusyId(id)
    try {
      await post(`/v1/story/stories/${id}/versions/${versionId}/restore`)
      setVersions((prev) => ({ ...prev, [id]: [] }))
      toast.show('已恢复该版本（旧版本均保留）')
      load(); await loadVersions(id)
    } catch (e: any) { toast.show(e.message, 'err') }
    finally { setBusyId('') }
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
      {stories.length === 0 ? <Empty icon="✎" text="还没有故事，去「故事生成」写第一篇吧" /> : stories.map((s) => {
        const vs = versions[s.id] || []
        const sel = compare[s.id] || [null, null]
        const pick = (idx: number, val: string) => {
          const next: [string | null, string | null] = [...sel] as any
          next[idx] = val
          setCompare((p) => ({ ...p, [s.id]: next }))
        }
        return (
          <div className="story-manage" key={s.id}>
            <div className="story-manage-head" style={{ flexWrap: 'wrap', gap: 8 }}>
              <div><b>{s.title || '无标题'}</b> <span className="chip">{s.status}</span> <span className="chip">{s.visibility === 'private' ? '仅自己' : s.visibility === 'family' ? '家庭可见' : '公开'}</span></div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <button className="btn sm ghost" onClick={() => onOpenInStudio(s)}>在工作室打开</button>
                <button className="btn sm ghost" onClick={() => toggle(s.id)}>版本 ({vs.length || '…'})</button>
                <button className="btn sm ghost" onClick={() => removeStory(s.id)}>删除</button>
              </div>
            </div>
            {expanded === s.id && (
              <div style={{ marginTop: 10 }}>
                {busyId === s.id && <Loading text="处理中…" />}
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
                  <select className="select" style={{ width: 140 }} value={regenMode[s.id] || 'first_person'} onChange={(e) => setRegenMode((p) => ({ ...p, [s.id]: e.target.value }))}>
                    {MODES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                  <button className="btn sm purple" onClick={() => regenerateStory(s.id)} disabled={busyId === s.id}>重新生成该风格</button>
                  <select className="select" style={{ width: 110 }} value={s.visibility} onChange={(e) => changeVisibility(s.id, e.target.value)}>
                    <option value="private">仅自己</option><option value="family">家庭可见</option><option value="public">公开</option>
                  </select>
                </div>
                {!versions[s.id] ? <Loading text="加载版本…" /> : vs.length === 0 ? (
                  <Empty icon="◷" text="暂无版本，先重新生成一个风格" />
                ) : (
                  <>
                    <div style={{ fontSize: 12, color: '#5b6b85', marginBottom: 8 }}>
                      版本对比：
                      <select className="select" style={{ width: 150, display: 'inline-block', margin: '0 6px' }} value={sel[0] || ''} onChange={(e) => pick(0, e.target.value)}>
                        <option value="">版本 A</option>{vs.map((v) => <option key={v.id} value={v.id}>v{v.version_no} · {modeLabel(v.mode)}</option>)}
                      </select>
                      <select className="select" style={{ width: 150, display: 'inline-block' }} value={sel[1] || ''} onChange={(e) => pick(1, e.target.value)}>
                        <option value="">版本 B</option>{vs.map((v) => <option key={v.id} value={v.id}>v{v.version_no} · {modeLabel(v.mode)}</option>)}
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
                        {vs.map((v) => <div key={v.id} className="version-item" style={{ flexWrap: 'wrap', gap: 6 }}>
                          <span className="chip">v{v.version_no} · {modeLabel(v.mode)}</span>
                          <span style={{ fontSize: 12, color: '#5b6b85' }}>{v.is_ai ? `${v.provider} / ${v.model}` : '人工编辑'} · {fmtTime(v.created_at)}</span>
                          <button className="btn sm ghost" onClick={() => restoreVersion(s.id, v.id)} disabled={busyId === s.id}>恢复此版</button>
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
