"""核对只读 PULSE 归档报告，并生成展示页的证据摘要。

用法：python scripts/build_pulse_evidence.py --research-root PATH_TO_UQCLASSIFIER
不修改研究仓库；展示值是归档结果摘要，不代表本次重新运行模型。
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "overview": "experiments/orchid_diagnostic/analysis/README.md",
    "diagnostic": "experiments/orchid_diagnostic/analysis/20261012_212455_primary161/REPORT.md",
    "panel": "experiments/orchid_diagnostic/analysis/clarification_panel_20261013_232133/REPORT.md",
    "validation": "experiments/orchid_diagnostic/analysis/uq_policy_validation_v2_20261015_001912/REPORT.md",
    "review": "experiments/orchid_diagnostic/analysis/evaluation_review_20261019/summary.json",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--research-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.research_root.resolve()
    files = {key: root / relative for key, relative in SOURCES.items()}
    content = {key: path.read_text(encoding="utf-8") for key, path in files.items()}
    checks = {
        "diagnostic": ["161", "8,050", "83.79%", "76.46%", "77.70%", "81.30%", "64.97%"],
        "panel": ["31 案例", "1,240", "63.55%", "87.10%", "12/15/4"],
        "overview": ["520案例", "10,400", "74.7885%", "79.5385%", "76.5000%", "75.9577%", "+0.5423", "−0.2592"],
    }
    for key, snippets in checks.items():
        for snippet in snippets:
            if snippet not in content[key]:
                raise ValueError(f"证据口径未通过核对：{SOURCES[key]} 缺少 {snippet}")

    evidence = {
        "researchAsOf": "2026-10-19",
        "evidenceType": "只读归档结果摘要；本次未重新生成代码或训练模型",
        "diagnostic": {
            "baseTasks": 161, "conditions": 5, "candidates": 8050,
            "originalTasks": 164, "excludedForInputMismatch": 3,
            "rows": [
                {"condition": "明确需求", "reliability": 83.79, "uq": 0.1349},
                {"condition": "词汇歧义", "reliability": 76.46, "uq": 0.1564},
                {"condition": "语义歧义", "reliability": 77.70, "uq": 0.1379},
                {"condition": "句法歧义", "reliability": 81.30, "uq": 0.1479},
                {"condition": "模糊表述", "reliability": 64.97, "uq": 0.1524},
            ],
            "interpretation": "语义歧义可靠性下降，但 UQ 增量很小；低生成波动不能排除稳定错误理解。",
        },
        "panel": {
            "selectedCases": 31, "baseTasks": 27, "arms": 124, "candidates": 1240,
            "originalReliability": 63.55, "clarifiedReliability": 87.10,
            "improved": 12, "unchanged": 15, "worsened": 4,
            "limitation": "分层选择且使用知情模拟用户，主要审阅机制和负收益，不能外推为总体平均收益。",
        },
        "budget": {
            "baseTasks": 130, "ambiguousCases": 520, "newCandidates": 10400, "mainClarifications": 128,
            "noClarification": 74.7885, "allClarification": 79.5385,
            "topUq": 76.5000, "uniformRandomExpectation": 75.9577,
            "differencePp": 0.5423, "clusterCi95Pp": [-0.2592, 1.4121],
            "improved": 65, "unchanged": 429, "worsened": 26,
            "interpretation": "全量澄清观察到收益；同预算高 UQ 优先相对随机的优势区间跨零，尚未确立。",
        },
        "catalog": {"metricCandidates": 8, "riskConditionCandidates": 6,
                    "counting": "组合指标、同源变换和同一参数化规则族须去重；候选数不等于合同合格数。"},
        "openItems": [
            "正式分类器权重和独立准确率证据未齐，生成前识别性能不能报告为已验证。",
            "部分结构差异历史值受哈希顺序影响；复现时需固定环境和版本。",
            "测试适配器曾修订并限定范围重评；冻结结果与修订结果分开保存。",
            "指标和规则尚需独立计数、预定阈值和独立任务上的预测验证。",
            "当前展示和内部函数检查不代替外部专家测试、第三方测评或合同验收。",
        ],
        "sources": [{"key": key, "pathWithinUqclassifier": SOURCES[key],
                     "sha256": hashlib.sha256(files[key].read_bytes()).hexdigest()}
                    for key in SOURCES],
    }
    output = ROOT / "dist/pulse-evidence.json"
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output} from {len(files)} read-only sources")


if __name__ == "__main__":
    main()
