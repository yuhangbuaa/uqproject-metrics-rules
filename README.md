# 项目指标库与规则库中期检查展示页

此目录用于智能软件决策不确定性项目的中期检查展示，呈现不确定性度量指标库与不确定性感知—预测规则库的候选条目。`dist/` 可由静态服务器托管：`index.html` 是项目目录，`pulse.html` 和 `evidence.html` 分别展示 PULSE 与 PlanCoder 的研究进展和证据，`catalog.json` 是当前条目数据源。`pulse_metrics.py` 与 `dist/pulse-functions.mjs` 单独封装需求端条目；`dist/catalog-functions.mjs` 保留统一导入入口。点击“查看函数定义”会打开 `functions.html` 并定位所选函数。

## 本地展示

安装 Python 3.10 或以上版本后，双击 `start-local.cmd`，或运行 `python server.py --port 4173`，再打开 [本地展示页](http://127.0.0.1:4173/)；[PULSE 成果页](http://127.0.0.1:4173/pulse.html)可直接进入需求端材料。无需 npm 或数据库；服务器与计算接口只依赖 Python 标准库。完整演示需复制 `dist/`、`server.py`、`plancoder_metrics.py`、`pulse_metrics.py`、`start-local.cmd`。纯静态服务器仍支持目录和浏览器本地试算，HTTP API 需要 `server.py`。

## 数据口径

页面把“候选数量”和合同目标分开显示。保留 PULSE 的8项指标和6条风险条件，新增 PlanCoder 的4项指标、3条风险预测假设和3条修复策略，共12项指标候选、12条规则或策略。**不代表独立条目计数已经核定或合同指标已经达标**。质量评分不等于失败概率，S-I04与P-I02是同源方差变换，S-R01至S-R03属于同一参数化规则族，修复策略与预测规则分列。10项指标、5种规则的目标沿用原目录配置，最终以协议及项目组核定为准。状态A表示实现与记录，B表示待独立验证，C表示机制或假设候选。

每个条目在页面上分开显示**函数入口**和**研究证据**，并标明研究来源。需求端独立模块封装 8 项指标的计算口径与 6 个规则条目的条件判断（P-R02/P-R03 共用同一个类别判断函数），并提供按编号调用的 `evaluate_metric` / `evaluate_rule` 和 `evaluatePulseMetric` / `evaluatePulseRule`。规则函数只返回是否触发，不输出经过校准的失败概率。P-I01 的浏览器函数接收固定版本的 CodeBLEU 相似度回调；按编号调用和 HTTP API 只聚合外部已算好的两两相似度，必须提供实现版本，本项目服务不运行 CodeBLEU。

在本地页面的浏览器控制台可试用纯计算函数：

```js
const { assertionPassInstability, pulseUq, evaluatePulseRule } = await import('./pulse-functions.mjs');
const instability = assertionPassInstability([0, 0.5, 1]);
const uq = pulseUq(0.4, instability);
const flag = evaluatePulseRule('P-R01', { previousBatchUq: uq, threshold: 0.5 });
console.log({ instability, uq, flag });
```

Python 中可直接导入 `from pulse_metrics import evaluate_metric, evaluate_rule`，以 `P-I01` 至 `P-I08`、`P-R01` 至 `P-R06` 编号调用。输入字段与本地 HTTP API 相同。展示页的 14 组 JSON 均为合成试算输入，并非研究实验记录。

后续接真实数据库时，可让接口返回与 `catalog.json` 相同的 `meta`、`metrics`、`rules` 结构，或在 `app.js` 的 `init()` 中加一层字段映射。每项应保留编号、来源、函数入口、定义、数据依赖、适用范围、证据、限制与负责人核定状态。不要直接将候选状态改成“已完成”。

PULSE现有条目及其证据说明保留。PlanCoder原草稿 `drafts/plan-paper-candidates_20261021.json` 作为历史材料；本次经论文和代码核对后的条目已加入 `dist/catalog.json`，并区分论文报告值、历史记录复算与本次新增接口实现。

## PULSE 成果与接口

[PULSE 成果与证据](http://127.0.0.1:4173/pulse.html) 沿用 PlanCoder 成果页的结构，展示受控歧义诊断、31 案例探索性澄清面板、130 题固定预算验证、需求端条目试算和待核事项。`dist/pulse-evidence.json` 摘录只读研究备份中的归档结果及五份来源文件哈希。高 UQ 优先相对随机的优势区间跨零；正式分类器权重、独立准确率与规则预测验证尚未齐全。页面不把候选数量视为合同达标数。

```text
GET  /api/v1/metrics?sourceKey=pulse
GET  /api/v1/rules?sourceKey=pulse
GET  /api/v1/pulse/evidence
POST /api/v1/metrics/P-I02/evaluate
POST /api/v1/rules/P-R04/evaluate
```

```powershell
$body = @{passRates = @(0, 0.5, 1)} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:4173/api/v1/metrics/P-I02/evaluate' -ContentType 'application/json; charset=utf-8' -Body $body
```

如研究备份更新，用 `python scripts/build_pulse_evidence.py --research-root PATH_TO_UQCLASSIFIER` 重新核对并生成证据摘要；脚本只读研究备份。`python scripts/enrich_pulse_catalog.py` 可补齐展示目录中的合成试算输入。

## PlanCoder 成果与接口

[成果与证据](http://127.0.0.1:4173/evidence.html) 展示三阶段方法、两模型四数据集结果及待核事项；[接口文档](http://127.0.0.1:4173/api.html) 提供交互调用和OpenAPI下载。

```text
GET  /api/v1/health
GET  /api/v1/catalog
GET  /api/v1/metrics?sourceKey=plancoder
GET  /api/v1/rules?sourceKey=plancoder
GET  /api/v1/metrics/S-I01
POST /api/v1/metrics/S-I04/evaluate
POST /api/v1/rules/S-R04/evaluate
POST /api/v1/plans/decision
POST /api/v1/plans/score
GET  /api/v1/evidence
GET  /api/v1/openapi.json
```

```powershell
$body = @{passRates = @(0, 0.5, 1, 0.5, 0.5)} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:4173/api/v1/metrics/S-I04/evaluate' -ContentType 'application/json; charset=utf-8' -Body $body
```

返回总体方差0.1，固定ddof=0；不是已经复算论文RQ1的原始五次采样记录。P-I01接口聚合外部提供的CodeBLEU相似度，需声明实现版本；本服务不运行CodeBLEU。

S-I01至S-I03在页面上提供异步模型评分函数、调用示例和完整模块下载。函数接收 `apiKey`、`baseUrl`、`model`、`problem`、`plan`，可行性函数额外接收非空 `visibleTests` 数组。调用方在 Node.js 18+ 中使用 `await` 获得模型实际生成的 `value`（0～1）、`rationale`、`dimension`、`evaluator`、`rubricVersion` 和 `usage`，无需预先提供分数。模型服务需支持 `/chat/completions` 请求和相应 JSON 返回结构；浏览器直接调用需服务支持跨域。函数不保存或返回 API Key。

```js
import { planFeasibility, planRelevance, planClarity } from './dist/catalog-functions.mjs';

const options = {
  apiKey: process.env.PLAN_JUDGE_API_KEY,
  baseUrl: process.env.PLAN_JUDGE_BASE_URL,
  model: process.env.PLAN_JUDGE_MODEL,
  problem: '编写 add(a, b)，返回两个整数的和。',
  plan: '接收两个整数，将它们相加并返回结果。'
};
const feasibility = await planFeasibility({ ...options, visibleTests: ['assert add(1, 2) == 3'] });
const relevance = await planRelevance(options);
const clarity = await planClarity(options);
console.log({ feasibility, relevance, clarity });
```

`POST /api/v1/metrics/S-I01/evaluate` 至 `S-I03/evaluate` 继续校验已有 `review` 评分记录。另一个入口 `POST /api/v1/plans/score` 使用服务端环境变量调用模型：

```powershell
$env:PLAN_JUDGE_ENABLED = '1'
$env:PLAN_JUDGE_API_KEY = 'YOUR_API_KEY'
$env:PLAN_JUDGE_MODEL = 'YOUR_MODEL'
$env:PLAN_JUDGE_BASE_URL = 'https://YOUR_PROVIDER/v1'
python server.py
```

服务端环境变量未配置时，`/api/v1/plans/score` 返回503；可下载的评分函数使用自己的输入配置，不依赖本地 Python 服务。真实评分按维度独立调用，只有可行性接收可见测试；相关性和清晰度仅接收任务与计划。此实现依据论文定义补充，不冒充论文原始评分脚本。页面中的任务、评分记录和阈值示例均为合成输入。本次测试使用模拟模型响应，未调用外部模型。

## 证据复算与检查

```powershell
python scripts/build_plancoder_catalog.py --research-root .. --paper 'PATH_TO_PAPER.pdf'
python scripts/build_openapi.py
python -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/catalog-functions.test.mjs
python scripts/run_checks.py --node 'PATH_TO_NODE_EXECUTABLE'
```

历史复算忽略summary，按task_id保留文件最后一条记录，不依据成败选优，原研究文件不改写。32份文件的哈希和结果保存在 `dist/plancoder-evidence.json`；重复、合并来源及失败调用零计量等事项显式保留。RQ1、RQ2、人工盲评及消融原始材料尚未齐全，不宣称已独立复算。

当前通过 Python 28 项和 JavaScript 13 项内部检查，记录在 `dist/selftest-results.json`。四份 PlanCoder 材料及四份 PULSE 对应材料位于 `deliverables/中期检查材料_20261022/`；基本信息和经费留空，专家结论与签字未预填。详见 [中期检查准备说明](docs/中期检查准备说明.md)。模板审计与渲染中间件位于忽略目录 `.work/midterm/`。未发布远程网站或推送Gitee。
