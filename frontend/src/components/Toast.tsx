import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'

type Ctx = { show: (msg: string, kind?: 'ok' | 'err') => void }
const ToastCtx = createContext<Ctx>({ show: () => {} })

export function ToastProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<{ msg: string; kind: string } | null>(null)
  const show = useCallback((msg: string, kind: 'ok' | 'err' = 'ok') => {
    setState({ msg, kind })
    setTimeout(() => setState(null), 3200)
  }, [])
  return (
    <ToastCtx.Provider value={{ show }}>
      {children}
      {state && <div className={`toast ${state.kind}`}>{state.msg}</div>}
    </ToastCtx.Provider>
  )
}

export const useToast = () => useContext(ToastCtx)
