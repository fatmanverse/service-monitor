import { GitBranch, Plus, Trash2 } from 'lucide-react'
import { Button } from '../../ui/Button'
import { Select } from '../../ui/Select'
import { isLeaf, type RuleGroup, type RuleProbe } from './healthRule'
import type { HealthRule } from '../../types'

interface RuleEditorProps {
  rule: HealthRule
  probes: RuleProbe[]
  onChange: (rule: HealthRule) => void
}

/**
 * Recursive editor for the nested AND/OR health rule. Each node renders itself
 * and delegates child edits upward by rebuilding its own subtree, so the whole
 * structure stays immutable.
 */
export function RuleEditor({ rule, probes, onChange }: RuleEditorProps) {
  const enabled = probes.filter((probe) => probe.enabled)

  if (isLeaf(rule)) {
    return <RuleLeafNode rule={rule} enabled={enabled} onChange={onChange} />
  }
  return <RuleGroupNode rule={rule} probes={probes} enabled={enabled} onChange={onChange} />
}

function RuleLeafNode({
  rule,
  enabled,
  onChange,
}: {
  rule: { probe: string }
  enabled: RuleProbe[]
  onChange: (rule: HealthRule) => void
}) {
  /** Pairs this leaf with another probe to form a group the backend accepts. */
  function convertToGroup() {
    const partner = enabled.find((probe) => probe.key !== rule.probe)
    if (!partner) return
    onChange({ op: 'AND', children: [rule, { probe: partner.key }] })
  }

  return (
    <div className="rule-node rule-leaf">
      <GitBranch size={16} aria-hidden />
      <Select
        value={rule.probe}
        aria-label="选择探活项"
        onChange={(event) => onChange({ probe: event.target.value })}
      >
        {enabled.map((probe) => (
          <option key={probe.key} value={probe.key}>
            {probe.name}
          </option>
        ))}
      </Select>
      <Button
        variant="ghost"
        size="sm"
        disabled={enabled.length < 2}
        title={enabled.length < 2 ? '至少需要两个启用探活项' : undefined}
        onClick={convertToGroup}
      >
        转为组合
      </Button>
    </div>
  )
}

function RuleGroupNode({
  rule,
  probes,
  enabled,
  onChange,
}: {
  rule: RuleGroup
  probes: RuleProbe[]
  enabled: RuleProbe[]
  onChange: (rule: HealthRule) => void
}) {
  function replaceChild(index: number, child: HealthRule) {
    onChange({
      ...rule,
      children: rule.children.map((item, itemIndex) => (itemIndex === index ? child : item)),
    })
  }

  function removeChild(index: number) {
    const children = rule.children.filter((_, itemIndex) => itemIndex !== index)
    // A group needs two children; collapse into the survivor instead.
    onChange(children.length === 1 ? children[0] : { ...rule, children })
  }

  function addLeaf() {
    const fallback = enabled[0]?.key ?? ''
    onChange({ ...rule, children: [...rule.children, { probe: fallback }] })
  }

  function addGroup() {
    const first = enabled[0]?.key ?? ''
    const second = enabled[1]?.key ?? first
    onChange({
      ...rule,
      children: [...rule.children, { op: 'AND', children: [{ probe: first }, { probe: second }] }],
    })
  }

  return (
    <div className="rule-node rule-group">
      <div className="rule-toolbar">
        <Select
          value={rule.op}
          aria-label="组合方式"
          onChange={(event) => onChange({ ...rule, op: event.target.value as RuleGroup['op'] })}
        >
          <option value="AND">全部满足 AND</option>
          <option value="OR">任一满足 OR</option>
        </Select>
        <Button variant="ghost" size="sm" icon={<Plus size={15} />} onClick={addLeaf}>
          探活项
        </Button>
        <Button
          variant="ghost"
          size="sm"
          icon={<Plus size={15} />}
          disabled={enabled.length < 2}
          onClick={addGroup}
        >
          嵌套组合
        </Button>
      </div>
      <div className="rule-children">
        {rule.children.map((child, index) => (
          <div className="rule-child" key={index}>
            <RuleEditor
              rule={child}
              probes={probes}
              onChange={(next) => replaceChild(index, next)}
            />
            {rule.children.length > 2 && (
              <Button
                variant="ghost"
                size="icon"
                aria-label="移除该节点"
                onClick={() => removeChild(index)}
              >
                <Trash2 size={15} />
              </Button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
