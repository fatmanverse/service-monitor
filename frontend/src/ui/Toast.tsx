import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, Info } from 'lucide-react'
import type { ReactNode } from 'react'

export type ToastTone = 'success' | 'danger' | 'info'

interface Toast {
  id: number
  tone: ToastTone
  title: string
  detail?: string
}

type ToastInput = Omit<Toast, 'id'>

const ToastContext = createContext<((toast: ToastInput) => void) | null>(null)

const TONE_ICON: Record<ToastTone, ReactNode> = {
  success: <CheckCircle2 size={17} />,
  danger: <AlertTriangle size={17} />,
  info: <Info size={17} />,
}

const DISMISS_AFTER_MS = 5000

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(1)

  const push = useCallback((toast: ToastInput) => {
    const id = nextId.current++
    setToasts((current) => [...current, { ...toast, id }])
    window.setTimeout(() => {
      setToasts((current) => current.filter((item) => item.id !== id))
    }, DISMISS_AFTER_MS)
  }, [])

  const value = useMemo(() => push, [push])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-viewport" role="region" aria-live="polite" aria-label="通知">
        {toasts.map((toast) => (
          <div key={toast.id} className="ui-toast" data-tone={toast.tone}>
            {TONE_ICON[toast.tone]}
            <div className="ui-toast-body">
              <div className="ui-toast-title">{toast.title}</div>
              {toast.detail && <span>{toast.detail}</span>}
            </div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const push = useContext(ToastContext)
  if (!push) throw new Error('useToast must be used inside ToastProvider')
  return push
}
