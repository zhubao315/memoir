import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'

type Ctx = { show: (msg: string, kind?: 'ok' | 'err') => void }
const ToastCtx = createContext<Ctx>({ show: () => {} })

export function ToastProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<{ msg: string; kind: string } | null>(null)
  const timer = useRef<number | null>(null)
  const show = useCallback((msg: string, kind: 'ok' | 'err' = 'ok') => {
    setState({ msg, kind })
    if (timer.current) window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setState(null), 3200)
  }, [])
  useEffect(() => () => { if (timer.current) window.clearTimeout(timer.current) }, [])
  return (
    <ToastCtx.Provider value={{ show }}>
      {children}
      {state && <div className={`toast ${state.kind}`}>{state.msg}</div>}
    </ToastCtx.Provider>
  )
}

export const useToast = () => useContext(ToastCtx)
