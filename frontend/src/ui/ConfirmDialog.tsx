import { Button } from './Button'
import { Modal } from './Modal'

interface ConfirmDialogProps {
  title: string
  message: string
  confirmLabel?: string
  /** `danger` for irreversible actions, `primary` for benign confirmations. */
  tone?: 'danger' | 'primary'
  busy?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmDialog({
  title,
  message,
  confirmLabel = '确认删除',
  tone = 'danger',
  busy = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <Modal
      title={title}
      size="sm"
      busy={busy}
      onClose={onCancel}
      footer={
        // Cancel comes first so the focus trap lands there rather than on the
        // destructive action.
        <>
          <Button onClick={onCancel} disabled={busy}>
            取消
          </Button>
          <Button variant={tone} onClick={onConfirm} loading={busy}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <p className="confirm-message">{message}</p>
    </Modal>
  )
}
