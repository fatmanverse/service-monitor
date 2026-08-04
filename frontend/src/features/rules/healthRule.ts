import type { HealthRule } from '../../types'

export interface RuleProbe {
  key: string
  name: string
  enabled: boolean
}

export type RuleLeaf = Extract<HealthRule, { probe: string }>
export type RuleGroup = Extract<HealthRule, { op: 'AND' | 'OR' }>

export function isLeaf(rule: HealthRule): rule is RuleLeaf {
  return 'probe' in rule
}

function enabledKeys(probes: RuleProbe[]): string[] {
  return probes.filter((probe) => probe.enabled).map((probe) => probe.key)
}

function probeLabel(key: string, probes: RuleProbe[]): string {
  return probes.find((probe) => probe.key === key)?.name || key
}

function collectKeys(rule: HealthRule, keys: string[]): void {
  if (isLeaf(rule)) {
    keys.push(rule.probe)
    return
  }
  for (const child of rule.children) collectKeys(child, keys)
}

/**
 * Mirrors the backend invariants in `health_rules.validate_rule`: every enabled
 * probe must appear exactly once, groups need at least two children, and no
 * leaf may reference a disabled or unknown probe. Returns a display message for
 * the first violation, or null when the rule is valid.
 *
 * The backend remains the authority; this only avoids a round trip and lets the
 * form point at the offending probe.
 */
export function validateRule(rule: HealthRule, probes: RuleProbe[]): string | null {
  const structureError = validateStructure(rule)
  if (structureError) return structureError

  const keys: string[] = []
  collectKeys(rule, keys)

  const counts = new Map<string, number>()
  for (const key of keys) counts.set(key, (counts.get(key) ?? 0) + 1)

  const duplicate = [...counts.entries()].find(([, count]) => count > 1)
  if (duplicate) {
    return `探活项“${probeLabel(duplicate[0], probes)}”在规则中重复出现。`
  }

  const allowed = new Set(enabledKeys(probes))
  const unknown = keys.find((key) => !allowed.has(key))
  if (unknown) {
    return `规则引用了不存在或已禁用的探活项“${probeLabel(unknown, probes)}”。`
  }

  const missing = [...allowed].find((key) => !counts.has(key))
  if (missing) {
    return `启用探活项“${probeLabel(missing, probes)}”尚未加入规则。`
  }

  return null
}

function validateStructure(rule: HealthRule): string | null {
  if (isLeaf(rule)) {
    return rule.probe ? null : '规则叶子必须引用有效探活项。'
  }
  if (rule.children.length < 2) {
    return '组合节点至少需要两个子节点。'
  }
  for (const child of rule.children) {
    const error = validateStructure(child)
    if (error) return error
  }
  return null
}

/** Flat AND over every enabled probe — the rule the backend always accepts. */
export function buildDefaultRule(probes: RuleProbe[]): HealthRule {
  const keys = enabledKeys(probes)
  if (keys.length <= 1) return { probe: keys[0] ?? '' }
  return { op: 'AND', children: keys.map((probe) => ({ probe })) }
}

/**
 * Repairs a rule after the probe list changed, preserving the operators the user
 * chose instead of discarding the tree. Leaves referencing removed or disabled
 * probes are dropped, groups left with one child collapse into it, and probes
 * that no longer appear are appended so the result satisfies validateRule.
 */
export function syncRuleWithProbes(rule: HealthRule, probes: RuleProbe[]): HealthRule {
  const allowed = enabledKeys(probes)
  const kept = new Set<string>()
  const pruned = pruneRule(rule, new Set(allowed), kept)
  const missing = allowed.filter((key) => !kept.has(key)).map((probe) => ({ probe }))

  if (!pruned) return buildDefaultRule(probes)
  if (missing.length === 0) return pruned
  if (isLeaf(pruned)) return { op: 'AND', children: [pruned, ...missing] }
  return { ...pruned, children: [...pruned.children, ...missing] }
}

function pruneRule(
  rule: HealthRule,
  allowed: Set<string>,
  kept: Set<string>,
): HealthRule | null {
  if (isLeaf(rule)) {
    if (!allowed.has(rule.probe) || kept.has(rule.probe)) return null
    kept.add(rule.probe)
    return rule
  }

  const children = rule.children
    .map((child) => pruneRule(child, allowed, kept))
    .filter((child): child is HealthRule => child !== null)

  if (children.length === 0) return null
  if (children.length === 1) return children[0]
  return { ...rule, children }
}

/** Renders the rule as readable Chinese, e.g. `进程存活 且 (HTTP 或 健康检查)`. */
export function describeRule(rule: HealthRule, probes: RuleProbe[]): string {
  if (isLeaf(rule)) return probeLabel(rule.probe, probes)
  return formatGroup(rule, probes, false)
}

function formatGroup(rule: HealthRule, probes: RuleProbe[], nested: boolean): string {
  if (isLeaf(rule)) return probeLabel(rule.probe, probes)
  const joined = rule.children
    .map((child) => formatGroup(child, probes, true))
    .join(rule.op === 'AND' ? ' 且 ' : ' 或 ')
  return nested ? `(${joined})` : joined
}
