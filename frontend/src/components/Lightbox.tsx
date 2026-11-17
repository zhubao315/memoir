import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'

type Preview = { url: string; alt: string; kind: 'image' | 'audio' | 'video' }
type Ctx = { open: (url: string, alt?: string, kind?: Preview['kind']) => void }
const LightboxCtx = createContext<Ctx>({ open: () => {} })

export function LightboxProvider({ children }: { children: ReactNode }) {
  const [preview, setPreview] = useState<Preview | null>(null)
  const open = useCallback(
    (url: string, alt = '预览', kind: Preview['kind'] = 'image') => setPreview({ url, alt, kind }),
    [],
  )
  const close = useCallback(() => setPreview(null), [])

  useEffect(() => {
    if (!preview) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') close() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [preview, close])

  return (
    <LightboxCtx.Provider value={{ open }}>
      {children}
      {preview && (
        <div className="lightbox" onClick={close} role="dialog" aria-modal="true" aria-label="媒体预览">
          <div className="lightbox-panel" onClick={(e) => e.stopPropagation()}>
            <button className="lightbox-close" onClick={close} aria-label="关闭">×</button>
            {preview.kind === 'image' && <img src={preview.url} alt={preview.alt} />}
            {preview.kind === 'audio' && (
              <div className="lightbox-player">
                <div className="lightbox-player-icon">◉</div>
                <audio src={preview.url} controls autoPlay />
              </div>
            )}
            {preview.kind === 'video' && <video src={preview.url} controls autoPlay style={{ maxWidth: '90vw', maxHeight: '80vh' }} />}
            <div className="lightbox-caption">{preview.alt}</div>
          </div>
        </div>
      )}
    </LightboxCtx.Provider>
  )
}

export const useLightbox = () => useContext(LightboxCtx)
