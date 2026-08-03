from collections import Counter
from typing import Dict, List, Set


class HealthRuleError(ValueError):
    pass


def collect_probe_keys(rule: dict) -> List[str]:
    if set(rule) == {"probe"}:
        probe = rule["probe"]
        if not isinstance(probe, str) or not probe:
            raise HealthRuleError("规则叶子必须引用有效探活项")
        return [probe]
    if set(rule) != {"op", "children"}:
        raise HealthRuleError("规则节点只能包含 op 和 children")
    if rule["op"] not in {"AND", "OR"}:
        raise HealthRuleError("规则操作符只支持 AND 或 OR")
    children = rule["children"]
    if not isinstance(children, list) or len(children) < 2:
        raise HealthRuleError("AND/OR 节点至少需要两个子节点")
    keys: List[str] = []
    for child in children:
        if not isinstance(child, dict):
            raise HealthRuleError("规则子节点必须是对象")
        keys.extend(collect_probe_keys(child))
    return keys


def validate_rule(rule: dict, enabled_probe_keys: Set[str]) -> None:
    keys = collect_probe_keys(rule)
    counts = Counter(keys)
    duplicates = sorted(key for key, count in counts.items() if count != 1)
    if duplicates:
        raise HealthRuleError(f"探活项在规则中重复出现：{', '.join(duplicates)}")
    referenced = set(keys)
    missing = sorted(enabled_probe_keys - referenced)
    unknown = sorted(referenced - enabled_probe_keys)
    if missing:
        raise HealthRuleError(f"启用探活项未加入规则：{', '.join(missing)}")
    if unknown:
        raise HealthRuleError(f"规则引用了不存在或未启用的探活项：{', '.join(unknown)}")


def evaluate_rule(rule: dict, results: Dict[str, bool]) -> bool:
    if set(rule) == {"probe"}:
        probe = rule["probe"]
        if probe not in results:
            raise HealthRuleError(f"缺少探活结果：{probe}")
        return results[probe]
    if set(rule) != {"op", "children"} or rule["op"] not in {"AND", "OR"}:
        raise HealthRuleError("在线规则结构无效")
    if not isinstance(rule["children"], list) or len(rule["children"]) < 2:
        raise HealthRuleError("AND/OR 节点至少需要两个子节点")
    values = [evaluate_rule(child, results) for child in rule["children"]]
    return all(values) if rule["op"] == "AND" else any(values)
