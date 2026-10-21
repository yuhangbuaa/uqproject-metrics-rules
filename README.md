# 项目指标库与规则库中期检查展示页

此目录用于智能软件决策不确定性项目的中期检查展示，呈现不确定性度量指标库与不确定性感知—预测规则库的候选条目。`dist/` 是可直接由静态服务器托管的页面：`index.html` 负责结构，`styles.css` 负责样式，`app.js` 负责筛选与详情交互，`catalog.json` 是当前条目数据源，`catalog-functions.mjs` 提供可复用的计算与条件判断函数。点击“查看函数定义”会打开 `functions.html`，由它按 UTF-8 显式解码并定位到所选函数。

## 本地展示

安装 Python 3.10 或以上版本后，双击 `start-local.cmd`，或运行 `python server.py --port 4173`，再打开 [本地展示页](http://127.0.0.1:4173/)。无需 npm 或数据库；服务器与计算接口只依赖 Python 标准库。完整演示需复制 `dist/`、`server.py`、`plancoder_metrics.py`、`start-local.cmd`。纯静态服务器仍支持目录和浏览器本地试算，HTTP API 需要 `server.py`。

## 数据口径

页面把“候选数量”和合同目标分开显示。保留 PULSE 的8项指标和6条风险条件，新增 PlanCoder 的4项指标、3条风险预测假设和3条修复策略，共12项指标候选、12条规则或策略。**不代表独立条目计数已经核定或合同指标已经达标**。质量评分不等于失败概率，S-I04与P-I02是同源方差变换，S-R01至S-R03属于同一参数化规则族，修复策略与预测规则分列。10项指标、5种规则的目标沿用原目录配置，最终以协议及项目组核定为准。状态A表示实现与记录，B表示待独立验证，C表示机制或假设候选。

每个条目在页面上分开显示**函数入口**和**研究证据**，并标明研究来源。页面附带的函数模块已封装 8 项指标的计算口径与 5 个规则条件函数（P-R02/P-R03 共用一个）；规则函数只返回是否触发，不输出经过校准的失败概率。P-I01 的函数负责 CodeBLEU 两两聚合，仍需调用方提供固定版本的 CodeBLEU 相似度函数。

在本地页面的浏览器控制台可试用纯计算函数：

```js
const { assertionPassInstability, pulseUq } = await import('./catalog-functions.mjs');
const instability = assertionPassInstability([0, 0.5, 1]);
const uq = pulseUq(0.4, instability);
console.log({ instability, uq });
```

后续接真实数据库时，可让接口返回与 `catalog.json` 相同的 `meta`、`metrics`、`rules` 结构，或在 `app.js` 的 `init()` 中加一层字段映射。每项应保留编号、来源、函数入口、定义、数据依赖、适用范围、证据、限制与负责人核定状态。不要直接将候选状态改成“已完成”。

PULSE现有条目及其证据说明保留。PlanCoder原草稿 `drafts/plan-paper-candidates_20261021.json` 作为历史材料；本次经论文和代码核对后的条目已加入 `dist/catalog.json`，并区分论文报告值、历史记录复算与本次新增接口实现。

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

S-I01至S-I03的离线接口校验带理由、评分器和rubric版本的已有评分记录，不伪造语义评分。真实模型评分由调用方配置服务端环境变量后启用：

```powershell
$env:PLAN_JUDGE_ENABLED = '1'
$env:PLAN_JUDGE_API_KEY = 'YOUR_API_KEY'
$env:PLAN_JUDGE_MODEL = 'YOUR_MODEL'
$env:PLAN_JUDGE_BASE_URL = 'https://YOUR_PROVIDER/v1'
python server.py
```

未配置时返回503。真实评分按维度独立调用，只有可行性接收可见测试；相关性和清晰度仅接收任务与计划。此接口是本次依据论文定义补充的实现，不冒充论文原始评分脚本。页面评分和阈值示例均为合成输入。本次测试未调用外部模型。

## 证据复算与检查

```powershell
python scripts/build_plancoder_catalog.py --research-root .. --paper 'PATH_TO_PAPER.pdf'
python scripts/build_openapi.py
python -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/catalog-functions.test.mjs
python scripts/run_checks.py --node 'PATH_TO_NODE_EXECUTABLE'
```

历史复算忽略summary，按task_id保留文件最后一条记录，不依据成败选优，原研究文件不改写。32份文件的哈希和结果保存在 `dist/plancoder-evidence.json`；重复、合并来源及失败调用零计量等事项显式保留。RQ1、RQ2、人工盲评及消融原始材料尚未齐全，不宣称已独立复算。

本轮通过Python24项和JavaScript6项检查，记录在 `dist/selftest-results.json`。四份模板衍生DOCX位于 `deliverables/中期检查材料_20261022/`；基本信息和经费留空，专家结论与签字未预填。详见 [中期检查准备说明](docs/中期检查准备说明.md)。模板审计与渲染中间件位于忽略目录 `.work/midterm/`。未发布远程网站或推送Gitee。
