import { useEffect, useRef, useState } from 'react'
import { api, get, post, put } from '../../services/api'
import { Card, Empty, Loading } from '../../components/ui'
import { useLightbox } from '../../components/Lightbox'
import { useToast } from '../../components/Toast'

type Phase = 'idle' | 'recording' | 'uploading' | 'transcribing' | 'done' | 'failed'

interface Transcript {
  id: string
  content: string
  engine?: string | null
  is_corrected?: boolean
  created_at?: string | null
}

const PHASE_LABEL: Record<Phase, string> = {
  idle: '就绪', recording: '录音中', uploading: '上传中',
  transcribing: '转写中', done: '完成', failed: '失败',
}
const STEPS: Phase[] = ['recording', 'uploading', 'transcribing', 'done']
const stepIndex = (p: Phase) => STEPS.indexOf(p)

export function VoiceStudio() {
  const [phase, setPhase] = useState<Phase>('idle')
  const [seconds, setSeconds] = useState(0)
  const [audioUrl, setAudioUrl] = useState('')       // 本地录音 blob 预览地址
  const [playUrl, setPlayUrl] = useState('')         // 服务端原始录音签名播放地址
  const [blob, setBlob] = useState<Blob | null>(null)
  const [error, setError] = useState('')
  const [transcripts, setTranscripts] = useState<Transcript[]>([])
  const [draft, setDraft] = useState('')
  const [saving, setSaving] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [story, setStory] = useState<any>(null)
  const recorder = useRef<MediaRecorder | null>(null)
  const chunks = useRef<Blob[]>([])
  const timer = useRef<number | null>(null)
  const toast = useToast()
  const lightbox = useLightbox()

  // 当前选中的（最新）逐字稿
  const current = transcripts[0]
  useEffect(() => {
    if (current) setDraft(current.content)
  }, [current?.id]) // 仅在切换到不同逐字稿时重置草稿

  const stopTimer = () => { if (timer.current) window.clearInterval(timer.current); timer.current = null }

  const start = async () => {
    setError(''); setStory(null); setTranscripts([]); setDraft(''); setPlayUrl('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mr = new MediaRecorder(stream, { mimeType: MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/mp4' })
      chunks.current = []
      mr.ondataavailable = e => { if (e.data.size) chunks.current.push(e.data) }
      mr.onstart = () => {
        setPhase('recording'); setSeconds(0)
        timer.current = window.setInterval(() => setSeconds(s => s + 1), 1000)
      }
      mr.onstop = () => {
        stopTimer()
        const b = new Blob(chunks.current, { type: mr.mimeType })
        setBlob(b); setAudioUrl(URL.createObjectURL(b)); setPhase('idle')
        stream.getTracks().forEach(t => t.stop())
      }
      // 30 分钟上限（对齐 Remento 体验）
      mr.start()
      window.setTimeout(() => { if (mr.state === 'recording') mr.stop() }, 30 * 60 * 1000)
      recorder.current = mr
    } catch (e: any) {
      setPhase('failed'); setError('无法访问麦克风：' + (e?.message || '') + '（录音需要 HTTPS 或 localhost）')
      toast.show('无法访问麦克风，请检查浏览器权限', 'err')
    }
  }
  const stop = () => { if (recorder.current?.state === 'recording') recorder.current.stop() }

  // 拉取录音详情（含逐字稿、真实引擎名与原始录音播放地址）
  const loadDetail = async (recordingId: string) => {
    const detail: any = await get(`/v1/story/recordings/${recordingId}`)
    setTranscripts(detail.transcripts || [])
    setPlayUrl(detail.play_url || '')
    return detail
  }

  const upload = async () => {
    if (!blob) return toast.show('请先录音', 'err')
    setError(''); setPhase('uploading')
    try {
      const fd = new FormData()
      fd.append('file', blob, `voice-${Date.now()}.webm`)
      // 复用统一 api 客户端：自动带 Bearer、自动处理 FormData 与错误 detail
      const media: any = await api('/v1/media/upload', { method: 'POST', body: fd })
      setPhase('transcribing')
      const rec: any = await post('/v1/story/recordings', { media_asset_id: media.id })

      let detail: any = null
      for (let i = 0; i < 15; i++) {
        await new Promise(r => setTimeout(r, 600))
        detail = await loadDetail(rec.id)
        if (detail.recording?.status === 'transcribed') break
        if (detail.recording?.status === 'failed') {
          setPhase('failed'); setError(detail.recording?.error || '转录失败，请重试')
          toast.show('转录失败：' + (detail.recording?.error || '未知错误'), 'err')
          return
        }
      }
      if (detail?.recording?.status === 'transcribed') {
        setPhase('done')
        toast.show('录音已保存，原始文件永久保留')
      } else {
        // 任务可能仍在进行，提示稍后刷新而非假装已完成
        setPhase('transcribing')
        toast.show('转录任务仍在进行，稍后刷新本页查看逐字稿')
      }
    } catch (e: any) {
      setPhase('failed'); setError(e.message || '上传或转录失败')
      toast.show(e.message || '操作失败', 'err')
    }
  }

  // 人工修正逐字稿：后端保留原始记录，另存为修正副本
  const saveTranscript = async () => {
    if (!current || !draft.trim()) return
    setSaving(true)
    try {
      const saved: any = await put(`/v1/story/transcripts/${current.id}`, { content: draft })
      toast.show(saved?.message || '逐字稿已保存（原始转写保持不变）')
    } catch (e: any) { toast.show(e.message, 'err') }
    finally { setSaving(false) }
  }

  const makeStory = async () => {
    if (!draft.trim()) return toast.show('还没有可用的逐字稿', 'err')
    setGenerating(true)
    try {
      const m: any = await post('/v1/memories', { title: '口述回忆', raw_content: draft, source: 'recording' })
      const s: any = await post('/v1/story/stories/generate', { mode: 'first_person', source_memory_id: m.id })
      setStory(s)
      toast.show('已从口述内容生成故事（可在「故事生成」切换风格）')
    } catch (e: any) { toast.show(e.message, 'err') }
    finally { setGenerating(false) }
  }

  const mm = String(Math.floor(seconds / 60)).padStart(2, '0')
  const ss = String(seconds % 60).padStart(2, '0')
  const phaseIdx = stepIndex(phase)

  return (
    <div className="grid grid-2">
      <Card title="Voice Studio · 语音录制">
        <p style={{ color: '#5b6b85', fontSize: 13, marginBottom: 18 }}>
          适合不擅长打字的讲述者。点击录音，说出你的故事，AI 会转录并帮你写成文章。
        </p>

        {/* 清晰的阶段指示：录音中 / 上传中 / 转写中 / 完成 / 失败 */}
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 14 }}>
          {STEPS.map((p, i) => (
            <span
              key={p}
              className="chip"
              style={{
                background: phase === 'failed' && i === phaseIdx ? '#fee2e2' : i <= phaseIdx ? '#e4ecff' : '#f3f4f6',
                color: phase === 'failed' && i === phaseIdx ? '#b91c1c' : i <= phaseIdx ? 'var(--electric-blue)' : '#9ca3af',
              }}
            >
              {i + 1}. {PHASE_LABEL[p]}
            </span>
          ))}
        </div>

        <div style={{ textAlign: 'center', padding: '10px 0' }}>
          <button
            className={`rec-btn ${phase === 'recording' ? 'recording' : ''}`}
            onClick={phase === 'recording' ? stop : start}
            disabled={phase === 'uploading' || phase === 'transcribing'}
            aria-label={phase === 'recording' ? '停止录音' : '开始录音'}
          >
            {phase === 'recording' ? '■' : '●'}
          </button>
          <div style={{ fontSize: 26, fontVariantNumeric: 'tabular-nums', marginTop: 14 }}>{mm}:{ss}</div>
          <div style={{ color: '#5b6b85', fontSize: 13 }}>状态：{PHASE_LABEL[phase]}</div>
          <div className="wave">{Array.from({ length: 28 }).map((_, i) => (
            <i key={i} style={{ height: phase === 'recording' ? 8 + ((i * 7) % 26) : 6 }} />
          ))}</div>
        </div>

        {error && (
          <div style={{ marginTop: 12, padding: 10, background: '#fee2e2', color: '#b91c1c', borderRadius: 8, fontSize: 13 }}>
            ✕ {error}
          </div>
        )}

        {(audioUrl || playUrl) && (
          <div style={{ marginTop: 16, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {audioUrl && (
              <button className="btn sm ghost" onClick={() => lightbox.open(audioUrl, '本次录音（本地预览）', 'audio')}>
                ▶ 播放本次录音
              </button>
            )}
            {playUrl && (
              <button className="btn sm ghost" onClick={() => lightbox.open(playUrl, '原始录音（媒体库）', 'audio')}>
                ▶ 播放原始录音
              </button>
            )}
          </div>
        )}
        {(phase === 'uploading' || phase === 'transcribing') && <Loading text={phase === 'uploading' ? '正在上传录音…' : 'AI 正在转写，请稍候…'} />}
        {blob && phase === 'idle' && (
          <button className="btn primary" style={{ marginTop: 12 }} onClick={upload}>上传并转录</button>
        )}
        {phase === 'failed' && <button className="btn primary" style={{ marginTop: 12 }} onClick={upload}>重试上传与转录</button>}
      </Card>

      <Card title="转录与故事">
        {!current && !story && phase !== 'transcribing' ? (
          <Empty icon="◉" text="录音、上传、转录后，这里会显示逐字稿与生成的故事" />
        ) : (
          <div>
            {!current && phase === 'transcribing' && <Loading text="等待逐字稿生成…" />}
            {current && (
              <>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                  <h4 style={{ margin: 0 }}>逐字稿</h4>
                  <span className="chip">转写引擎：{current.engine || '未知'}</span>
                  {current.is_corrected && <span className="chip">人工修正版</span>}
                </div>
                {current.engine === 'mock' && (
                  <p style={{ fontSize: 12, color: '#9a3412', margin: '0 0 10px' }}>
                    当前为离线 Mock 转录占位文本；配置真实 ASR 引擎后将显示真实转写内容。
                  </p>
                )}
                <textarea
                  className="textarea"
                  style={{ minHeight: 160 }}
                  value={draft}
                  onChange={e => setDraft(e.target.value)}
                  placeholder="可直接编辑逐字稿，修改后保存"
                />
                <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
                  <button className="btn primary" onClick={saveTranscript} disabled={saving || !draft.trim()}>
                    {saving ? '保存中…' : '保存逐字稿修正'}
                  </button>
                  <button className="btn purple" onClick={makeStory} disabled={generating || !draft.trim()}>
                    {generating ? '生成中…' : '生成第一人称故事'}
                  </button>
                </div>
                {transcripts.length > 1 && (
                  <div style={{ marginTop: 12, fontSize: 12, color: '#5b6b85' }}>
                    共 {transcripts.length} 条转写记录（原始 + 修正副本均保留）。
                  </div>
                )}
              </>
            )}
            {story && (
              <div style={{ marginTop: 16 }}>
                <h4>生成的故事</h4>
                <div className="card" style={{ boxShadow: 'none' }}>
                  <b>{story.title}</b>
                  <p style={{ fontSize: 13, color: '#5b6b85', marginTop: 6 }}>
                    已保存到「我的故事」，可在故事工作室一键切换叙事风格或编辑版本。
                  </p>
                </div>
              </div>
            )}
          </div>
        )}
      </Card>
    </div>
  )
}
