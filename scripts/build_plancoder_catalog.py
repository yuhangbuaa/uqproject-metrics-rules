"""从 PlanCoder 论文定义与本地历史记录构建展示条目和证据索引。"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "PlanCoder 计划质量研究"
RUBRIC = "plancoder-plan-quality-1.0"


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_catalog():
    path = ROOT / "dist/catalog.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for kind in ("metrics", "rules"):
        data[kind] = [x for x in data[kind] if not x["id"].startswith("S-")]
        for x in data[kind]:
            x["sourceKey"] = "pulse"
            x["entryType"] = "不确定性度量" if kind == "metrics" else "候选风险条件"
            x["countingStatus"] = "独立条目与验收计数待核定"
            x["apiPath"] = f"/api/v1/{kind}/{x['id']}/evaluate"
    quality = [
        ("S-I01", "计划可行性评分", "feasibility", "planFeasibility", "检查算法逻辑、步骤、边界约束，以及对可见测试预期输出的解释。", "任务描述、计划、可见测试，以及评分器输出与版本。", "0.293 / 0.158", "0.898", "0.052"),
        ("S-I02", "需求相关性评分", "relevance", "planRelevance", "检查计划是否对准编程目标、覆盖明确功能要求和重要约束。", "任务描述、计划，以及评分器输出与版本；该维度不提供测试。", "0.198 / 0.101", "0.866", "0.044"),
        ("S-I03", "计划清晰度评分", "clarity", "planClarity", "检查计划是否顺序清楚、无歧义、具体到可以转为实现。", "任务描述、计划，以及评分器输出与版本；该维度不提供测试。", "0.102 / 0.079", "0.839", "0.034"),
    ]
    for identifier, name, dimension, function, definition, inputs, correlation, ccc, mae in quality:
        data["metrics"].append({
            "id": identifier, "name": name, "group": "计划质量", "status": "B", "source": SOURCE, "sourceKey": "plancoder",
            "entryType": "计划质量评分", "summary": definition,
            "formula": f"s_{dimension} = Judge(task, plan{', visibleTests' if dimension == 'feasibility' else ''}) ∈ [0,1]；分数越高质量越好",
            "inputs": inputs, "scope": "独立 Python 编程任务的生成前计划评价；不读取隐藏测试与生成结果。",
            "functionSignature": f"{function}(review)",
            "functionNote": "离线函数校验并读取带理由和来源的评分；真实评分调用 POST /api/v1/plans/score，需自行配置模型。页面示例为合成输入。",
            "evidence": f"论文第4—7页：202个配对任务、404份计划；与测试通过率的 Pearson / Spearman 为 {correlation}。人工一致性分析包含100题200份计划，CCC={ccc}，MAE={mae}。这些为论文报告值，本仓库尚无原始评分与标注记录。",
            "limits": "属于计划质量评分，未校准为失败概率；本次实现是依据论文定义补充的评分接口，并非论文原始评分脚本。",
            "decision": "归档原始提示词、评分器版本、202题逐例评分和人工盲评记录，独立验证预测能力。",
            "apiPath": f"/api/v1/metrics/{identifier}/evaluate", "countingStatus": "计划质量信号候选；是否计入不确定性指标须项目组核定",
            "family": f"plan-quality-{dimension}",
            "inputExample": {"review": {"dimension": dimension, "score": 0.4, "rationale": "合成示例：用于验证接口格式，不是研究评分。", "evaluator": "synthetic-example", "rubricVersion": RUBRIC}},
        })
    data["metrics"].append({
        "id": "S-I04", "name": "同题代码通过率方差", "group": "生成稳定性", "status": "B", "source": SOURCE, "sourceKey": "plancoder",
        "entryType": "结果波动度量", "summary": "衡量同一任务多次生成代码在同一测试集上的通过率波动。",
        "formula": "Var(PR) = (1/K) Σᵢ(rᵢ − mean(r))²；本接口固定 ddof=0，K≥2，值域 [0,0.25]",
        "inputs": "同题、同测试条件下至少两次生成的逐候选测试通过率；论文实验为五次。",
        "scope": "离线评估代码生成稳定性；跨题汇总时先逐题计算，再对任务取平均。",
        "functionSignature": "planPassRateVariance(passRates)", "functionNote": "直接计算总体方差；与 P-I02 的归一化方差共享原始信息，不自动视为独立指标。",
        "evidence": "论文第3—4页表1使用通过率方差比较五种提示设置。论文尚未明确 ddof，原始逐次生成记录未在本仓库提供，本次公式不等于已经复算表1。",
        "limits": "全部成功和全部失败均可能方差为0；不能单独代表功能正确性或模型全部不确定性。",
        "decision": "核实原实验 ddof；与 P-I02 合并归类并明确计数。", "apiPath": "/api/v1/metrics/S-I04/evaluate",
        "countingStatus": "与 P-I02 同源；不得重复宣称独立能力", "family": "test-pass-variation", "inputExample": {"passRates": [0, 0.5, 1, 0.5, 0.5]},
    })
    for dimension_index, dimension in enumerate(("feasibility", "relevance", "clarity"), 1):
        identifier = f"S-R0{dimension_index}"
        chinese = {"feasibility": "可行性", "relevance": "相关性", "clarity": "清晰度"}[dimension]
        correlation = ["0.293 / 0.158", "0.198 / 0.101", "0.102 / 0.079"][dimension_index - 1]
        data["rules"].append({
            "id": identifier, "name": f"低计划{chinese}的后续实现风险", "group": "计划质量风险", "status": "C", "source": SOURCE, "sourceKey": "plancoder",
            "entryType": "预测假设", "summary": f"将低{chinese}评分作为后续代码质量风险的方向性提示。",
            "condition": f"生成代码前的 {dimension} 分数小于调用方预先提供的阈值。", "outcome": "提示后续代码可能存在功能失败或实现困难；不输出失败概率。",
            "inputs": f"S-I0{dimension_index} 的生成前评分，以及在独立训练数据上预先固定的阈值。",
            "functionSignature": "flagLowPlanQuality(score, threshold)", "functionNote": "只实现 score < threshold。页面中的0.6是演示参数，论文未给出经验证的阈值。",
            "evidence": f"论文表2报告与代码通过率的 Pearson / Spearman 为 {correlation}；相关性不等于阈值预测验证。",
            "limits": "没有独立预测集、已固定阈值、精确率/召回率或概率校准；三条规则属于同一参数化规则族。",
            "decision": "按任务划分训练和独立测试集，固定阈值并验证风险区分能力。",
            "apiPath": f"/api/v1/rules/{identifier}/evaluate", "countingStatus": "同一规则族的三个维度，不自动计为三种独立规则", "family": "low-plan-quality",
            "inputExample": {"score": 0.4, "threshold": 0.6},
        })
    strategies = [
        ("S-R04", "公开测试失败后的计划修复", "公开测试未全部通过，且已执行计划修复次数小于上限。", "修复计划并据此重新生成代码。", "shouldRepairPlan(context)", {"publicPassed": False, "planRepairs": 0, "codeRepairs": 0}),
        ("S-R05", "计划修复耗尽后的检索与代码修复", "公开测试仍失败，计划修复次数已达上限，代码修复次数尚未达上限。", "固定最终计划，按计划检索与重排示例，继续修复代码。", "shouldRetrieveAndRepair(context)", {"publicPassed": False, "planRepairs": 5, "codeRepairs": 0}),
        ("S-R06", "公开测试通过或预算耗尽后的停止", "公开测试全部通过，或两类修复预算均已耗尽。", "返回当前实现，并进行隐藏测试评估；公开测试通过不等于隐藏测试通过。", "shouldStopPlanCoder(context)", {"publicPassed": True, "planRepairs": 0, "codeRepairs": 0}),
    ]
    for identifier, name, condition, outcome, signature, example in strategies:
        data["rules"].append({
            "id": identifier, "name": name, "group": "分阶段修复控制", "status": "A", "source": SOURCE, "sourceKey": "plancoder", "entryType": "修复策略",
            "summary": outcome, "condition": condition, "outcome": outcome,
            "inputs": "公开测试通过标记、已执行计划/代码修复次数、配置预算；默认上限5次和6次。",
            "functionSignature": signature, "functionNote": "执行阶段条件判断；不运行生成代码、不调用模型、不替代隐藏测试。",
            "evidence": "论文第7—9页与 plancoder.py 的分阶段控制一致；现有两模型四数据集记录各覆盖929个任务。本次补充独立可调用条件函数与边界测试。",
            "limits": "属于响应与修复策略，不属于经过验证的质量预测规则；不与预测规则混同计数。",
            "decision": "专家按项目协议核定其成果类型，保留各阶段条件与运行记录。",
            "apiPath": f"/api/v1/rules/{identifier}/evaluate", "countingStatus": "策略条目，单列展示，不作为预测规则达标证明", "family": "plancoder-staged-repair", "inputExample": example,
        })
    for x in data["metrics"]:
        if x["id"] == "P-I02": x["family"] = "test-pass-variation"
    data["meta"].update({"asOf": "2026-10-22", "scope": "PULSE 需求端研究与 PlanCoder 计划质量研究", "schemaVersion": "1.1.0",
        "countingNote": "页面数量为候选条目；质量评分、同源变换、参数化规则族及修复策略须分别核定，不代表合同指标达标。",
        "contractNote": "10项指标、5种规则沿用现有目录配置；本次未取得协议原文，最终以协议及项目组核定为准。",
        "sources": [{"key": "pulse", "name": "PULSE 需求端研究"}, {"key": "plancoder", "name": SOURCE}],
        "plancoder": {"metrics": 4, "hypotheses": 3, "strategies": 3, "paperStatus": "论文稿；未提供录用证明", "evidenceUrl": "./plancoder-evidence.json"}})
    dump(path, data)


def build_evidence(research_root: Path, paper: Path | None):
    result = {"asOf": "2026-10-22", "method": "按 task_id 保留文件中最后一条任务记录，忽略 summary；不按成败选优。",
              "historicalOnly": True, "reexecutedGeneratedCode": False, "results": [], "issues": [],
              "paperOnly": {"rq1": "表1尚缺五次采样原始记录及脚本，未独立复算", "rq2": "202题404计划评分、人工标注与统计脚本未提供，未独立复算", "ablation": "表6与表7对照记录和源脚本未提供，未独立复算"},
              "paperReported": {"pearson": {"feasibility": 0.293, "relevance": 0.198, "clarity": 0.102}, "spearman": {"feasibility": 0.158, "relevance": 0.101, "clarity": 0.079}}}
    for model in ("gpt-5.4-mini", "gpt-5.6-luna"):
        for method in ("plancoder", "debatecoder", "lpw", "mapcoder"):
            for dataset in ("mbpp-et", "apps", "codecontests", "livecodebench"):
                if method == "mapcoder": path = research_root / f"mapcoder-main/outputs_{model}/{dataset}_{model}_full.jsonl"
                elif method == "lpw": path = research_root / f"outputs/lpw_{model}/{dataset}/{model}/lpw/probs._12_{model}_identification_full.jsonl"
                else: path = research_root / f"outputs/{method}_{model}/{dataset}_{model}_full.jsonl"
                if not path.exists():
                    result["issues"].append({"type": "missing_result", "file": str(path.relative_to(research_root))}); continue
                lines = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
                rows = [x for x in lines if not x.get("summary")]
                dedup = {x["task_id"]: x for x in rows}
                n = len(dedup)
                solved = sum(bool(x.get("pass@1", x.get("is_solved", False))) for x in dedup.values())
                record = {"method": method, "model": model, "dataset": dataset, "rawRows": len(rows), "tasks": n, "solved": solved,
                          "passAt1": solved / n, "meanTokens": sum(x.get("usage", {}).get("total_tokens", 0) for x in dedup.values()) / n,
                          "meanCalls": sum(x.get("usage", {}).get("llm_calls", 0) for x in dedup.values()) / n,
                          "meanSeconds": sum(x.get("elapsed_seconds", 0) for x in dedup.values()) / n,
                          "source": str(path.relative_to(research_root)).replace("\\", "/"), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                result["results"].append(record)
                if len(rows) != n:
                    result["issues"].append({"type": "duplicate_tasks", "source": record["source"], "rawRows": len(rows), "uniqueTasks": n, "resolution": "保留最后一条记录，保留原文件不修改"})
                for x in lines:
                    if x.get("left_file"):
                        result["issues"].append({"type": "merged_runs", "source": record["source"], "left": x["left_file"], "right": x["right_file"], "selection": x.get("selected_from"), "resolution": "原始选择规则待核查；本次不将其解释为单次独立运行"})
                zero = sum(not x.get("usage", {}).get("llm_calls") for x in dedup.values())
                if zero: result["issues"].append({"type": "zero_recorded_usage", "source": record["source"], "tasks": zero, "resolution": "失败调用可能未完整计入；不能解释为真实零成本"})
    corpus = research_root / "src/app/dataset/tianchi/swiftcoder_planning.json"
    result["retrievalPool"] = {"items": len(json.loads(corpus.read_text(encoding="utf-8"))), "sha256": hashlib.sha256(corpus.read_bytes()).hexdigest(),
        "modelsPresentHere": all((research_root / p).exists() for p in ("src/app/bge-embedding", "src/app/bge-reranker")), "overlapRemoval": "9430条与论文一致；去除21条APPS及跨库无重叠的原始审计清单尚待归档"}
    if paper and paper.exists(): result["paper"] = {"title": "What Makes a Good Plan for Effective Code Generation?", "filename": paper.name, "sha256": hashlib.sha256(paper.read_bytes()).hexdigest(), "status": "论文稿，未提供录用证明"}
    dump(ROOT / "dist/plancoder-evidence.json", result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--research-root", type=Path, default=ROOT.parent)
    parser.add_argument("--paper", type=Path)
    args = parser.parse_args()
    build_catalog()
    build_evidence(args.research_root, args.paper)
    print("Updated catalog and historical evidence index.")
