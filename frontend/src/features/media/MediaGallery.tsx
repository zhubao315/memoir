import { useEffect, useState } from 'react'

interface MediaItem {
  id: string
  file_name?: string
  mime_type?: string
  url?: string
  created_at?: string
}

/**
 * 媒体库占位视图：显示已上传的媒体，不伪造数据。
 * 原始 App.tsx 引用了缺失的 ./features/media/MediaGallery，导致 tsc 构建失败。
 */
export function MediaGallery() {
  const [items, setItems] = useState<MediaItem[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    const token = localStorage.getItem('memoir_token') || localStorage.getItem('token') || ''
    fetch('/api/media', {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.json()
      })
      .then((data: unknown) => {
        if (!active) return
        const list = Array.isArray(data)
          ? data
          : (data as { items?: MediaItem[] })?.items ?? []
        setItems(list)
      })
      .catch((err: Error) => {
        if (active) setError(err.message)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [])

  return (
    <section aria-label="媒体库">
      <h1>媒体库</h1>
      <p>当前账号下已上传的媒体文件。</p>
      {loading && <p>加载中…</p>}
      {error && <p role="alert">读取失败：{error}</p>}
      {!loading && !error && items.length === 0 && <p>还没有媒体文件。</p>}
      <ul>
        {items.map((item) => (
          <li key={item.id}>
            {item.url ? (
              <a href={item.url} target="_blank" rel="noreferrer">
                {item.file_name || item.id}
              </a>
            ) : (
              <span>{item.file_name || item.id}</span>
            )}
            {item.mime_type && <small> · {item.mime_type}</small>}
          </li>
        ))}
      </ul>
    </section>
  )
}
