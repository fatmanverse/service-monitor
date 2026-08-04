import { FieldLabel } from '../ui/Field'
import type { AlertConfig } from '../types'

interface AlertTargetPickerProps {
  label: string
  configs: AlertConfig[]
  selectedIds: number[]
  onToggle: (configId: number) => void
}

function describe(config: AlertConfig): string {
  if (!config.enabled) return '已停用'
  return config.webhook_configured ? '启用' : 'Webhook 未配置'
}

/**
 * Multi-select list of Feishu bots. An unselected target that is disabled or
 * missing its webhook cannot be picked, but an already-selected one stays
 * interactive so an existing association can always be removed.
 */
export function AlertTargetPicker({
  label,
  configs,
  selectedIds,
  onToggle,
}: AlertTargetPickerProps) {
  return (
    <div className="form-grid-wide">
      <FieldLabel>{label}</FieldLabel>
      <div className="option-list">
        {configs.length === 0 ? (
          <span className="option-empty">暂无飞书告警配置，请先前往告警管理新增。</span>
        ) : (
          configs.map((config) => {
            const selected = selectedIds.includes(config.id)
            const selectable = config.enabled && config.webhook_configured
            return (
              <label className="option-item" key={config.id}>
                <input
                  type="checkbox"
                  checked={selected}
                  disabled={!selected && !selectable}
                  onChange={() => onToggle(config.id)}
                />
                <span className="option-item-text">
                  <strong>{config.name}</strong>
                  <small>{describe(config)}</small>
                </span>
              </label>
            )
          })
        )}
      </div>
    </div>
  )
}
