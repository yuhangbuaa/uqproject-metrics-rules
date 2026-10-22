"""生成与本地服务一致的 OpenAPI 3.1 描述。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
catalog = json.loads((ROOT / "dist/catalog.json").read_text(encoding="utf-8"))
object_schema = {"type": "object", "additionalProperties": True}
response_schema = {"type": "object", "additionalProperties": True}


def operation(summary, post=False, example=None):
    value = {"summary": summary, "responses": {"200": {"description": "成功", "content": {"application/json": {"schema": response_schema}}}, "400": {"description": "JSON 或输入参数无效"}, "404": {"description": "未知条目或接口"}}}
    if post:
        value["requestBody"] = {"required": True, "content": {"application/json": {"schema": object_schema, **({"example": example} if example else {})}}}
        value["responses"].update({"413": {"description": "请求体过大"}, "415": {"description": "需要 application/json"}})
    return value


paths = {
    "/api/v1/health": {"get": operation("本地服务与评分服务配置状态")},
    "/api/v1/catalog": {"get": operation("完整指标与规则目录")},
    "/api/v1/evidence": {"get": operation("历史结果复算与证据索引")},
    "/api/v1/openapi.json": {"get": operation("本接口描述")},
    "/api/v1/plans/decision": {"post": operation("PlanCoder阶段决策 不执行代码", True, {"publicPassed": False, "planRepairs": 5, "codeRepairs": 0})},
    "/api/v1/plans/score": {"post": operation("调用外部模型生成计划质量评分 需配置环境变量", True, {"problem": "返回两数之和", "plan": "相加并返回", "visibleTests": ["assert add(1, 2) == 3"], "dimensions": ["feasibility", "relevance", "clarity"]})},
}
paths["/api/v1/plans/score"]["post"]["responses"].update({"503": {"description": "模型评分未配置"}, "502": {"description": "外部服务请求或返回解析失败"}})
for kind in ("metrics", "rules"):
    op = operation("查询条目列表并筛选")
    op["parameters"] = [{"name": key, "in": "query", "schema": {"type": "string"}, "required": False} for key in ("sourceKey", "status", "entryType")]
    paths[f"/api/v1/{kind}"] = {"get": op}
    for item in catalog[kind]:
        paths[f"/api/v1/{kind}/{item['id']}"] = {"get": operation(item["name"] + " 定义与证据")}
        post = operation(item["name"] + " 计算或条件判断", True, item.get("inputExample"))
        post["description"] = item.get("apiNote", item["inputs"]).rstrip("。") + "。" + item["limits"]
        paths[item["apiPath"]] = {"post": post}
document = {"openapi": "3.1.0", "info": {"title": "项目指标库与规则库本地接口", "version": "1.0.0", "description": "候选成果展示与复算接口。质量分数及规则标记不是校准后的失败概率。模型评分按维度独立调用，不向相关性与清晰度评分器提供测试。"}, "servers": [{"url": "http://127.0.0.1:4173", "description": "默认本地服务；也可使用当前站点源地址"}], "paths": paths}
(ROOT / "dist/openapi.json").write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Wrote {len(paths)} OpenAPI paths.")
