import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'

type Preview = { url: string; alt: string }
type Ctx = { open: (url: string, alt?: string) => void }
const LightboxCtx = createContext<Ctx>({ open: () => {} })

export function LightboxProvider({ children }: { children: ReactNode }) {
  const [preview, setPreview] = useState<Preview | null>(null)
  const open = useCallback((url: string, alt = '图片预览') => setPreview({ url, alt }), [])
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
        <div className="lightbox" onClick={close} role="dialog" aria-modal="true" aria-label="图片预览">
          <div className="lightbox-panel" onClick={(e) => e.stopPropagation()}>
            <button className="lightbox-close" onClick={close} aria-label="关闭">×</button>
            <img src={preview.url} alt={preview.alt} />
            <div className="lightbox-caption">{preview.alt}</div>
          </div>
        </div>
      )}
    </LightboxCtx.Provider>
  )
}

export const useLightbox = () => useContext(LightboxCtx)
