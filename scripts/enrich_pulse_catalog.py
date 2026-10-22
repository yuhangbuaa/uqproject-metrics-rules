"""为已有 PULSE 条目补充可编辑的合成试算输入。"""
from __future__ import annotations

import json
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "dist/catalog.json"
catalog = json.loads(path.read_text(encoding="utf-8"))
examples = {
    "P-I01": {"pairSimilarities": [0.8, 0.6, 0.7], "implementationVersion": "synthetic-example-not-real-CodeBLEU"},
    "P-I02": {"passRates": [0, 0.5, 1]},
    "P-I03": {"structuralDifference": 0.4, "instability": 0.2},
    "P-I04": {"codes": ["return a + b", "return b + a"]},
    "P-I05": {"successes": [True, False, True]},
    "P-I06": {"successes": [True, False, True]},
    "P-I07": {"codes": ["return a", "return a", "return b"]},
    "P-I08": {"ambiguousUq": 0.5, "clearUq": 0.2},
    "P-R01": {"previousBatchUq": 0.7, "threshold": 0.6},
    "P-R02": {"category": "vague"},
    "P-R03": {"category": "lexical"},
    "P-R04": {"semanticGapDetected": True, "uq": 0.2, "lowUqThreshold": 0.3},
    "P-R05": {"checks": {"premiseSupported": False, "selfContained": True,
                           "entailed": True, "historyConsistent": True,
                           "criticalConditionsComplete": True}},
    "P-R06": {"uq": 0.2, "lowUqThreshold": 0.3, "criticalConstraintMissing": True},
}
found = set()
for item in catalog["metrics"] + catalog["rules"]:
    if item.get("sourceKey") == "pulse":
        item["inputExample"] = examples[item["id"]]
        found.add(item["id"])
if found != set(examples):
    raise ValueError(f"PULSE 条目与示例不一致：{found ^ set(examples)}")
catalog["meta"]["pulse"] = {"metrics": 8, "riskConditions": 6,
                             "evidenceUrl": "./pulse-evidence.json",
                             "moduleUrl": "./pulse-functions.mjs"}
path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("Enriched 14 PULSE catalog entries")
