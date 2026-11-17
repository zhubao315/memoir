import type { ReactNode } from 'react'

export function Card({ title, extra, children }: { title?: string; extra?: ReactNode; children: ReactNode }) {
  return (
    <div className="card">
      {title && <div className="card-title"><span>{title}</span>{extra}</div>}
      {children}
    </div>
  )
}

export function Empty({ icon = '📖', text }: { icon?: string; text: string }) {
  return <div className="empty"><div className="ico">{icon}</div><div>{text}</div></div>
}

export function Loading({ text = '加载中…' }: { text?: string }) {
  return <div className="loading"><div className="spinner" />{text}</div>
}

export function Stat({ value, label, icon }: { value: ReactNode; label: string; icon?: string }) {
  return <div className="stat">{icon && <span className="a">{icon}</span>}<div className="v">{value ?? 0}</div><div className="l">{label}</div></div>
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return <div className="field"><label>{label}</label>{children}</div>
}
