"""PULSE 需求端候选指标和风险条件的纯计算入口。

调用方提供代码生成、测试、需求分类及澄清核对结果。本模块不运行
CodeBLEU、生成模型或分类器；规则输出仅是条件标记，不是失败概率。
"""
from __future__ import annotations

import math
from typing import Any


def _unit(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"{name} 必须是 [0,1] 内的有限数字")
    return float(value)


def _unit_list(values: Any, name: str) -> list[float]:
    if not isinstance(values, list) or not values:
        raise ValueError(f"{name} 必须是非空数值数组")
    return [_unit(value, name) for value in values]


def _booleans(values: Any, name: str) -> list[bool]:
    if not isinstance(values, list) or not values or any(not isinstance(value, bool) for value in values):
        raise ValueError(f"{name} 必须是非空布尔数组")
    return values


def _codes(values: Any) -> list[str]:
    if not isinstance(values, list) or not values or any(not isinstance(value, str) for value in values):
        raise ValueError("codes 必须是非空字符串数组")
    return values


def _flag(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} 必须是布尔值")
    return value


def codebleu_diversity(pair_similarities: Any, implementation_version: Any) -> dict:
    """P-I01：聚合调用方已计算的全部两两 CodeBLEU 相似度。"""
    scores = _unit_list(pair_similarities, "pairSimilarities")
    if not isinstance(implementation_version, str) or not implementation_version.strip():
        raise ValueError("需提供外部 CodeBLEU implementationVersion")
    return {"value": 1 - sum(scores) / len(scores), "implementationVersion": implementation_version,
            "interpretation": "聚合外部提供的全部两两相似度；本服务不运行 CodeBLEU"}


def assertion_pass_instability(pass_rates: Any) -> float:
    """P-I02：候选通过率的总体方差除以 0.25。"""
    values = _unit_list(pass_rates, "passRates")
    mean = sum(values) / len(values)
    return min(sum((value - mean) ** 2 for value in values) / len(values) / 0.25, 1)


def pulse_uq(structural_difference: Any, instability: Any) -> float:
    """P-I03：当前实验采用的等权组合，不是失败概率。"""
    return 0.5 * _unit(structural_difference, "structuralDifference") + 0.5 * _unit(instability, "instability")


def line_jaccard_diversity(codes: Any) -> float:
    """P-I04：去空行并逐行去首尾空白后的平均两两集合差异。"""
    values = _codes(codes)
    if len(values) < 2:
        return 0
    sets = [{line.strip() for line in code.splitlines() if line.strip()} for code in values]
    distances = [1 - len(left & right) / len(left | right) if left | right else 0
                 for i, left in enumerate(sets) for right in sets[i + 1:]]
    return sum(distances) / len(distances)


def outcome_entropy(successes: Any) -> float:
    """P-I05：同题候选的二元结果熵，单位 bit。"""
    values = _booleans(successes, "successes")
    p = sum(values) / len(values)
    return 0 if p in (0, 1) else -p * math.log2(p) - (1 - p) * math.log2(1 - p)


def outcome_variance(successes: Any) -> float:
    """P-I06：与 P-I05 使用同一个成功比例 p。"""
    values = _booleans(successes, "successes")
    p = sum(values) / len(values)
    return p * (1 - p)


def unique_code_ratio(codes: Any) -> float:
    """P-I07：代码字符串完全一致时判作重复。"""
    values = _codes(codes)
    return len(set(values)) / len(values)


def paired_uq_delta(ambiguous_uq: Any, clear_uq: Any) -> float:
    """P-I08：同题同测试条件下，歧义表述与明确表述的 UQ 差。"""
    return _unit(ambiguous_uq, "ambiguousUq") - _unit(clear_uq, "clearUq")


def flag_high_uq(previous_batch_uq: Any, threshold: Any) -> bool:
    """P-R01：判断上一批次 UQ 是否达到外部固定阈值。"""
    return _unit(previous_batch_uq, "previousBatchUq") >= _unit(threshold, "threshold")


def flag_ambiguity_category(category: Any, expected_category: str) -> bool:
    """P-R02/03：类别由外部需求识别器提供。"""
    if not isinstance(category, str):
        raise ValueError("category 必须是字符串")
    return category == expected_category


def flag_semantic_risk(semantic_gap_detected: Any, uq: Any, low_uq_threshold: Any) -> bool:
    """P-R04：关键语义缺口由外部检测；低波动不排除稳定错误。"""
    gap = _flag(semantic_gap_detected, "semanticGapDetected")
    value = _unit(uq, "uq")
    threshold = _unit(low_uq_threshold, "lowUqThreshold")
    return gap and value <= threshold


def flag_unsupported_clarification(checks: Any) -> bool:
    """P-R05：澄清回答的五项核对结果须由外部提供。"""
    if not isinstance(checks, dict):
        raise ValueError("checks 必须是对象")
    keys = ("premiseSupported", "selfContained", "entailed", "historyConsistent", "criticalConditionsComplete")
    values = [_flag(checks.get(key), key) for key in keys]
    return not all(values)


def flag_stable_misunderstanding(uq: Any, low_uq_threshold: Any, critical_constraint_missing: Any) -> bool:
    """P-R06：决定性约束缺失由外部核对，当前无已验证自动检测器。"""
    low = _unit(uq, "uq") <= _unit(low_uq_threshold, "lowUqThreshold")
    missing = _flag(critical_constraint_missing, "criticalConstraintMissing")
    return low and missing


METRICS = {
    "P-I02": lambda d: assertion_pass_instability(d.get("passRates")),
    "P-I03": lambda d: pulse_uq(d.get("structuralDifference"), d.get("instability")),
    "P-I04": lambda d: line_jaccard_diversity(d.get("codes")),
    "P-I05": lambda d: outcome_entropy(d.get("successes")),
    "P-I06": lambda d: outcome_variance(d.get("successes")),
    "P-I07": lambda d: unique_code_ratio(d.get("codes")),
    "P-I08": lambda d: paired_uq_delta(d.get("ambiguousUq"), d.get("clearUq")),
}

RULES = {
    "P-R01": lambda d: flag_high_uq(d.get("previousBatchUq"), d.get("threshold")),
    "P-R02": lambda d: flag_ambiguity_category(d.get("category"), "vague"),
    "P-R03": lambda d: flag_ambiguity_category(d.get("category"), "lexical"),
    "P-R04": lambda d: flag_semantic_risk(d.get("semanticGapDetected"), d.get("uq"), d.get("lowUqThreshold")),
    "P-R05": lambda d: flag_unsupported_clarification(d.get("checks")),
    "P-R06": lambda d: flag_stable_misunderstanding(d.get("uq"), d.get("lowUqThreshold"), d.get("criticalConstraintMissing")),
}


def evaluate_metric(identifier: str, data: dict) -> dict:
    """按条目编号复算指标；输入字段与 HTTP API 相同。"""
    if identifier == "P-I01":
        return codebleu_diversity(data.get("pairSimilarities"), data.get("implementationVersion"))
    if identifier not in METRICS:
        raise KeyError(identifier)
    return {"value": METRICS[identifier](data), "interpretation": "研究指标，不是经过校准的失败概率"}


def evaluate_rule(identifier: str, data: dict) -> dict:
    """按条目编号判断候选风险条件；不输出失败概率。"""
    if identifier not in RULES:
        raise KeyError(identifier)
    return {"triggered": RULES[identifier](data), "ruleType": "候选风险条件", "validatedThreshold": False,
            "interpretation": "仅判断条件；外部识别信号及阈值须另行验证，不输出失败概率"}
