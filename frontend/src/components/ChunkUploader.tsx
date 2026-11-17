import { useRef, useState } from 'react'
import { getToken } from '../services/api'
import { useToast } from './Toast'

type Progress = { name: string; done: number; total: number; error?: string; url?: string }

export function ChunkUploader({ onUploaded, memoryId }: { onUploaded?: () => void; memoryId?: string }) {
  const [queue, setQueue] = useState<Progress[]>([])
  const [dragging, setDragging] = useState(false)
  const input = useRef<HTMLInputElement>(null)
  const toast = useToast()

  const upload = async (file: File) => {
    const token = getToken()
    const headers = { Authorization: `Bearer ${token}` }
    setQueue((q) => [...q, { name: file.name, done: 0, total: 1 }])
    const idx = () => queue.length
    const update = (fn: (p: Progress) => Progress) =>
      setQueue((q) => q.map((p, i) => (p.name === file.name && p.total >= 1 ? fn(p) : p)))

    try {
      const initRes = await fetch('/api/v1/uploads/init', {
        method: 'POST', headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: file.name, size: file.size, mime_type: file.type || undefined, memory_id: memoryId || undefined }),
      })
      if (!initRes.ok) throw new Error((await initRes.json()).detail || '初始化失败')
      const init = await initRes.json()
      const total = init.total_chunks
      setQueue((q) => q.map((p) => (p.name === file.name ? { ...p, total } : p)))

      for (let i = 0; i < total; i++) {
        const chunk = file.slice(i * init.chunk_size, Math.min(file.size, (i + 1) * init.chunk_size))
        const res = await fetch(`/api/v1/uploads/${init.upload_id}/chunk?index=${i}`, {
          method: 'PUT', headers, body: chunk,
        })
        if (!res.ok) throw new Error((await res.json()).detail || `第 ${i + 1} 片上传失败`)
        setQueue((q) => q.map((p) => (p.name === file.name ? { ...p, done: i + 1 } : p)))
      }
      const done = await fetch(`/api/v1/uploads/${init.upload_id}/complete`, { method: 'POST', headers })
      if (!done.ok) throw new Error((await done.json()).detail || '合并失败')
      setQueue((q) => q.map((p) => (p.name === file.name ? { ...p, done: total, url: 'ok' } : p)))
      toast.show(`${file.name} 上传完成`)
      onUploaded?.()
    } catch (e: any) {
      setQueue((q) => q.map((p) => (p.name === file.name ? { ...p, error: e.message } : p)))
      toast.show(e.message, 'err')
    }
    void idx
  }

  const onFiles = (files: FileList | null) => { if (files) Array.from(files).forEach(upload) }

  return (
    <div
      className={`dropzone${dragging ? ' dragging' : ''}`}
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => { e.preventDefault(); setDragging(false); onFiles(e.dataTransfer.files) }}
    >
      <input ref={input} type="file" multiple hidden onChange={(e) => onFiles(e.target.files)} accept="image/*,video/*,audio/*,.pdf,.txt,.md" />
      <div className="dropzone-main" onClick={() => input.current?.click()}>
        <div className="dropzone-ico">⬆</div>
        <b>拖拽文件到这里，或点击选择</b>
        <span>支持照片 / 音频 / 视频 / 文档，分片上传，自动断点记录</span>
      </div>
      {queue.length > 0 && (
        <div className="upload-queue">
          {queue.map((p, i) => (
            <div key={i} className="upload-item">
              <div className="upload-name">{p.name}</div>
              <div className="progress-track"><div className="progress-fill" style={{ width: `${p.total ? (p.done / p.total) * 100 : 30}%`, background: p.error ? '#e05260' : undefined }} /></div>
              <div className="upload-meta">{p.error ? <span style={{ color: '#e05260' }}>{p.error}</span> : `${p.done}/${p.total} 分片`}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
