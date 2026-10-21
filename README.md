# 项目指标库与规则库中期检查展示页

此目录用于智能软件决策不确定性项目的中期检查展示，呈现不确定性度量指标库与不确定性感知—预测规则库的候选条目。`dist/` 是可直接由静态服务器托管的页面：`index.html` 负责结构，`styles.css` 负责样式，`app.js` 负责筛选与详情交互，`catalog.json` 是当前条目数据源，`catalog-functions.mjs` 提供可复用的计算与条件判断函数。点击“查看函数定义”会打开 `functions.html`，由它按 UTF-8 显式解码并定位到所选函数。

## 本地展示

安装 Python 3 后，双击 `start-local.cmd`，再打开 `http://127.0.0.1:4173/`。无需 Node.js、npm 或数据库。安装检查、手动启动和常见问题见 [本地运行环境说明](本地运行环境说明_20261021.md)。演示电脑只需复制 `dist/`、`start-local.cmd` 和环境说明文件。

## 数据口径

页面把“候选数量”和合同目标分开显示。现阶段录入的 8 个指标候选和 6 个规则候选来自 PULSE 需求端研究，**不代表项目库已收齐或达到合同要求**。状态 A 表示有实现和保存的实验记录，B 表示有实现或分析但仍待独立验证，C 表示机制候选；这些状态均不等于项目验收通过。

每个条目在页面上分开显示**函数入口**和**研究证据**，并标明研究来源。页面附带的函数模块已封装 8 项指标的计算口径与 5 个规则条件函数（P-R02/P-R03 共用一个）；规则函数只返回是否触发，不输出经过校准的失败概率。P-I01 的函数负责 CodeBLEU 两两聚合，仍需调用方提供固定版本的 CodeBLEU 相似度函数。

在本地页面的浏览器控制台可试用纯计算函数：

```js
const { assertionPassInstability, pulseUq } = await import('./catalog-functions.mjs');
const instability = assertionPassInstability([0, 0.5, 1]);
const uq = pulseUq(0.4, instability);
console.log({ instability, uq });
```

后续接真实数据库时，可让接口返回与 `catalog.json` 相同的 `meta`、`metrics`、`rules` 结构，或在 `app.js` 的 `init()` 中加一层字段映射。每项应保留编号、来源、函数入口、定义、数据依赖、适用范围、证据、限制与负责人核定状态。不要直接将候选状态改成“已完成”。

当前展示依据：[PULSE 候选清单](../材料草稿/PULSE指标与质量预测规则候选清单_20261020.md)。师兄论文的[条目审计](../材料草稿/PlanCoder论文指标规则审计_20261021.md)和 `drafts/plan-paper-candidates_20261021.json` 保留为待核材料，当前不在展示页或 `dist/catalog.json` 中。未来确认条目定义、可复算实现与证据后，再按同一数据结构加入。
