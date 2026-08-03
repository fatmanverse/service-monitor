import { GitBranch, Plus, Trash2 } from 'lucide-react'
import type { HealthRule } from './types'

type RuleProbe = { key: string; name: string; enabled: boolean }

function replaceChild(rule: Extract<HealthRule, { op: 'AND' | 'OR' }>, index: number, child: HealthRule) {
  return { ...rule, children: rule.children.map((item, itemIndex) => itemIndex === index ? child : item) }
}

export function RuleEditor({ rule, probes, onChange }: { rule: HealthRule; probes: RuleProbe[]; onChange: (rule: HealthRule) => void }) {
  const enabled = probes.filter((probe) => probe.enabled)
  if ('probe' in rule) {
    return <div className="rule-node rule-leaf"><GitBranch size={16} /><select value={rule.probe} onChange={(event) => onChange({ probe: event.target.value })}>{enabled.map((probe) => <option value={probe.key} key={probe.key}>{probe.name} ({probe.key})</option>)}</select><button type="button" className="ghost-button" disabled={enabled.length < 2} onClick={() => onChange({ op: 'AND', children: [rule, { probe: enabled.find((probe) => probe.key !== rule.probe)?.key || rule.probe }] })}>转为组合</button></div>
  }
  return <div className="rule-node rule-group"><div className="rule-toolbar"><select value={rule.op} onChange={(event) => onChange({ ...rule, op: event.target.value as 'AND' | 'OR' })}><option value="AND">全部满足 AND</option><option value="OR">任一满足 OR</option></select><button type="button" className="ghost-button" onClick={() => onChange({ ...rule, children: [...rule.children, { probe: enabled[0]?.key || '' }] })}><Plus size={15} />探活项</button><button type="button" className="ghost-button" onClick={() => onChange({ ...rule, children: [...rule.children, { op: 'AND', children: [{ probe: enabled[0]?.key || '' }, { probe: enabled[1]?.key || enabled[0]?.key || '' }] }] })}><Plus size={15} />组合</button></div><div className="rule-children">{rule.children.map((child, index) => <div className="rule-child" key={index}><RuleEditor rule={child} probes={probes} onChange={(next) => onChange(replaceChild(rule, index, next))} />{rule.children.length > 2 && <button type="button" className="danger-button" onClick={() => onChange({ ...rule, children: rule.children.filter((_, itemIndex) => itemIndex !== index) })}><Trash2 size={15} /></button>}</div>)}</div></div>
}

export function buildDefaultRule(probes: RuleProbe[]): HealthRule {
  const keys = probes.filter((probe) => probe.enabled).map((probe) => probe.key)
  if (keys.length === 1) return { probe: keys[0] }
  return { op: 'AND', children: keys.map((probe) => ({ probe })) }
}
