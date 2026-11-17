import { useRef, useState } from 'react'
import { get, post } from '../../services/api'
import { Card, Empty } from '../../components/ui'
import { useToast } from '../../components/Toast'

export function VoiceStudio() {
  const [recording, setRecording] = useState(false)
  const [seconds, setSeconds] = useState(0)
  const [audioUrl, setAudioUrl] = useState('')
  const [blob, setBlob] = useState<Blob | null>(null)
  const [status, setStatus] = useState('')
  const [transcript, setTranscript] = useState('')
  const [story, setStory] = useState<any>(null)
  const recorder = useRef<MediaRecorder | null>(null)
  const chunks = useRef<Blob[]>([])
  const timer = useRef<number | null>(null)
  const toast = useToast()

  const start = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mr = new MediaRecorder(stream, { mimeType: MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/mp4' })
      chunks.current = []
      mr.ondataavailable = e => { if (e.data.size) chunks.current.push(e.data) }
      mr.onstart = () => {
        setRecording(true); setSeconds(0); setStatus('正在录音…')
        timer.current = window.setInterval(() => setSeconds(s => s + 1), 1000)
      }
      mr.onstop = () => {
        setRecording(false)
        if (timer.current) window.clearInterval(timer.current)
        const b = new Blob(chunks.current, { type: mr.mimeType })
        setBlob(b); setAudioUrl(URL.createObjectURL(b)); setStatus('录音完成，可上传生成故事')
        stream.getTracks().forEach(t => t.stop())
      }
      // 30 分钟上限（对齐 Remento 体验）
      mr.start()
      window.setTimeout(() => { if (mr.state === 'recording') mr.stop() }, 30 * 60 * 1000)
      recorder.current = mr
    } catch (e: any) {
      toast.show('无法访问麦克风：' + e.message + '（录音需要 HTTPS 或 localhost）', 'err')
    }
  }
  const stop = () => { if (recorder.current?.state === 'recording') recorder.current.stop() }

  const upload = async () => {
    if (!blob) return toast.show('请先录音', 'err')
    try {
      setStatus('上传中…')
      const fd = new FormData()
      fd.append('file', blob, `voice-${Date.now()}.webm`)
      const res = await fetch('/api/v1/media/upload', {
        method: 'POST',
        headers: { Authorization: `Bearer ${localStorage.getItem('memoir_token')}` },
        body: fd,
      })
      if (!res.ok) throw new Error((await res.json()).detail || '上传失败')
      const media: any = await res.json()
      setStatus('创建转录任务…')
      const rec: any = await post('/v1/story/recordings', { media_asset_id: media.id })
      let detail: any = null
      for (let i = 0; i < 10; i++) {
        await new Promise(r => setTimeout(r, 600))
        detail = await get(`/v1/story/recordings/${rec.id}`)
        if (detail.recording?.status === 'transcribed') break
      }
      setTranscript(detail?.transcripts?.[0]?.content || '（转录任务仍在进行，稍后刷新查看）')
      setStatus('转录完成')
      toast.show('录音已保存，原始文件永久保留')
    } catch (e: any) { setStatus('失败：' + e.message); toast.show(e.message, 'err') }
  }

  const makeStory = async () => {
    if (!transcript) return toast.show('还没有转录文本', 'err')
    try {
      const m: any = await post('/v1/memories', { title: '口述回忆', raw_content: transcript, source: 'recording' })
      const s: any = await post('/v1/story/stories/generate', { mode: 'first_person', source_memory_id: m.id })
      setStory(s)
      toast.show('已从口述内容生成故事')
    } catch (e: any) { toast.show(e.message, 'err') }
  }

  const mm = String(Math.floor(seconds / 60)).padStart(2, '0')
  const ss = String(seconds % 60).padStart(2, '0')

  return (
    <div className="grid grid-2">
      <Card title="Voice Studio · 语音录制">
        <p style={{ color: '#5b6b85', fontSize: 13, marginBottom: 18 }}>
          适合不擅长打字的讲述者。点击录音，说出你的故事，AI 会转录并帮你写成文章。
        </p>
        <div style={{ textAlign: 'center', padding: '10px 0' }}>
          <button className={`rec-btn ${recording ? 'recording' : ''}`} onClick={recording ? stop : start}>
            {recording ? '■' : '●'}
          </button>
          <div style={{ fontSize: 26, fontVariantNumeric: 'tabular-nums', marginTop: 14 }}>{mm}:{ss}</div>
          <div style={{ color: '#5b6b85', fontSize: 13 }}>{status || '点击开始录音'}</div>
          <div className="wave">{Array.from({ length: 28 }).map((_, i) => (
            <i key={i} style={{ height: recording ? 8 + ((i * 7) % 26) : 6 }} />
          ))}</div>
        </div>
        {audioUrl && <audio src={audioUrl} controls style={{ width: '100%', marginTop: 16 }} />}
        {blob && <button className="btn primary" style={{ marginTop: 12 }} onClick={upload}>上传并转录</button>}
      </Card>
      <Card title="转录与故事">
        {!transcript && !story ? <Empty icon="◉" text="录音、上传、转录后，这里会显示逐字稿与生成的故事" /> : (
          <div>
            {transcript && <><h4 style={{ marginBottom: 8 }}>逐字稿（可修正，原始录音不变）</h4>
              <div className="msg ai" style={{ maxWidth: '100%' }}>{transcript}</div>
              <button className="btn purple" onClick={makeStory} style={{ marginTop: 10 }}>生成第一人称故事</button></>}
            {story && <div style={{ marginTop: 16 }}><h4>生成的故事</h4><div className="card" style={{ boxShadow: 'none' }}>{(story as any).title}</div></div>}
          </div>
        )}
      </Card>
    </div>
  )
}
