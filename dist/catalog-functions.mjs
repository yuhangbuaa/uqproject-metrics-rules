/**
 * 展示页使用的候选指标与规则条件函数。
 * 输入由调用者提供；本模块不读取研究仓库、运行生成模型或连接数据库。
 * 规则函数只返回条件标记，不给出经过校准的失败概率。
 */

function numbersInUnitInterval(values, name) {
  if (!Array.isArray(values) || values.some((value) => typeof value !== "number" || !Number.isFinite(value) || value < 0 || value > 1)) {
    throw new TypeError(`${name} 必须是 [0,1] 内有限数字的数组`);
  }
  return values;
}

function unitValue(value, name) {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0 || value > 1) {
    throw new TypeError(`${name} 必须是 [0,1] 内的有限数字`);
  }
  return value;
}

function strings(values, name) {
  if (!Array.isArray(values) || values.some((value) => typeof value !== "string")) {
    throw new TypeError(`${name} 必须是字符串数组`);
  }
  return values;
}

function booleans(values, name) {
  if (!Array.isArray(values) || values.some((value) => typeof value !== "boolean")) {
    throw new TypeError(`${name} 必须是布尔值数组`);
  }
  return values;
}

function meanPairwise(values, distance) {
  if (values.length < 2) return 0;
  let sum = 0;
  let count = 0;
  for (let i = 0; i < values.length; i += 1) {
    for (let j = i + 1; j < values.length; j += 1) {
      sum += distance(values[i], values[j]);
      count += 1;
    }
  }
  return sum / count;
}

/** P-I01：scorePair 须调用固定版本的 CodeBLEU，返回两份代码的 [0,1] 相似度。 */
export function codebleuDiversity(codes, scorePair) {
  strings(codes, "codes");
  if (typeof scorePair !== "function") throw new TypeError("需要 CodeBLEU 相似度函数 scorePair");
  return meanPairwise(codes, (a, b) => 1 - unitValue(scorePair(a, b), "CodeBLEU 相似度"));
}

/** P-I02：候选断言通过率的总体方差除以 0.25，上限为 1。 */
export function assertionPassInstability(passRates) {
  numbersInUnitInterval(passRates, "passRates");
  if (!passRates.length) return 0;
  const mean = passRates.reduce((sum, value) => sum + value, 0) / passRates.length;
  const variance = passRates.reduce((sum, value) => sum + (value - mean) ** 2, 0) / passRates.length;
  return Math.min(variance / 0.25, 1);
}

/** P-I03：当前受控实验的固定权重组合；不是失败概率。 */
export function pulseUq(structuralDifference, instability) {
  return 0.5 * unitValue(structuralDifference, "structuralDifference") + 0.5 * unitValue(instability, "instability");
}

/** P-I04：按去空行、逐行 trim 后的集合计算平均两两 Jaccard 差异。 */
export function lineJaccardDiversity(codes) {
  strings(codes, "codes");
  const lineSet = (code) => new Set(code.split(/\r\n|\n|\r/).filter((line) => line.trim()).map((line) => line.trim()));
  return meanPairwise(codes, (a, b) => {
    const left = lineSet(a);
    const right = lineSet(b);
    const union = new Set([...left, ...right]);
    if (!union.size) return 0;
    let intersection = 0;
    for (const line of left) if (right.has(line)) intersection += 1;
    return 1 - intersection / union.size;
  });
}

/** P-I05：K 次生成整体通过标记的二元熵，单位 bit。 */
export function outcomeEntropy(successes) {
  booleans(successes, "successes");
  if (!successes.length) return 0;
  const p = successes.filter(Boolean).length / successes.length;
  return p === 0 || p === 1 ? 0 : -p * Math.log2(p) - (1 - p) * Math.log2(1 - p);
}

/** P-I06：与 P-I05 使用同一个 p，独立计数待核。 */
export function outcomeVariance(successes) {
  booleans(successes, "successes");
  if (!successes.length) return 0;
  const p = successes.filter(Boolean).length / successes.length;
  return p * (1 - p);
}

/** P-I07：按代码字符串完全一致判断重复。 */
export function uniqueCodeRatio(codes) {
  strings(codes, "codes");
  return codes.length ? new Set(codes).size / codes.length : 0;
}

/** P-I08：同题、同测试条件下的配对 UQ 差值。 */
export function pairedUqDelta(ambiguousUq, clearUq) {
  return unitValue(ambiguousUq, "ambiguousUq") - unitValue(clearUq, "clearUq");
}

/** P-R01：只判断旧批次 UQ 是否达到外部固定阈值。 */
export function flagHighUq(previousBatchUq, threshold) {
  return unitValue(previousBatchUq, "previousBatchUq") >= unitValue(threshold, "threshold");
}

/** P-R02/P-R03：category 必须来自外部需求类型识别。 */
export function flagAmbiguityCategory(category, expectedCategory) {
  if (typeof category !== "string" || typeof expectedCategory !== "string" || !expectedCategory) {
    throw new TypeError("category 和 expectedCategory 必须是类别字符串");
  }
  return category === expectedCategory;
}

/** P-R04：关键语义缺口须由外部检测；低 UQ 不消除该风险提示。 */
export function flagSemanticRisk(semanticGapDetected, uq, lowUqThreshold) {
  if (typeof semanticGapDetected !== "boolean") throw new TypeError("semanticGapDetected 必须是布尔值");
  return semanticGapDetected && unitValue(uq, "uq") <= unitValue(lowUqThreshold, "lowUqThreshold");
}

/** P-R05：checks 的各项结果由外部证据核对器或人工审核提供。 */
export function flagUnsupportedClarification(checks) {
  const keys = ["premiseSupported", "selfContained", "entailed", "historyConsistent", "criticalConditionsComplete"];
  if (!checks || typeof checks !== "object" || keys.some((key) => typeof checks[key] !== "boolean")) {
    throw new TypeError(`checks 必须包含布尔字段：${keys.join(", ")}`);
  }
  return keys.some((key) => !checks[key]);
}

/** P-R06：决定性约束缺失须由外部检测，当前无经验证的自动检测器。 */
export function flagStableMisunderstanding(uq, lowUqThreshold, criticalConstraintMissing) {
  if (typeof criticalConstraintMissing !== "boolean") throw new TypeError("criticalConstraintMissing 必须是布尔值");
  return unitValue(uq, "uq") <= unitValue(lowUqThreshold, "lowUqThreshold") && criticalConstraintMissing;
}

/** S-I01/02/03：校验带来源的评分记录；不会在本地伪造模型判断。 */
function planQualityReview(review, dimension) {
  if (!review || typeof review !== "object" || review.dimension !== dimension) throw new TypeError(`review.dimension 必须为 ${dimension}`);
  for (const key of ["rationale", "evaluator", "rubricVersion"]) {
    if (typeof review[key] !== "string" || !review[key].trim()) throw new TypeError(`review.${key} 不能为空`);
  }
  return unitValue(review.score, "review.score");
}

export function planFeasibility(review) {
  return planQualityReview(review, "feasibility");
}

export function planRelevance(review) {
  return planQualityReview(review, "relevance");
}

export function planClarity(review) {
  return planQualityReview(review, "clarity");
}

/** S-I04：至少两次同题生成，固定总体方差 ddof=0；不是失败概率。 */
export function planPassRateVariance(passRates) {
  numbersInUnitInterval(passRates, "passRates");
  if (passRates.length < 2) throw new TypeError("至少需要两次生成的通过率");
  const mean = passRates.reduce((sum, value) => sum + value, 0) / passRates.length;
  return passRates.reduce((sum, value) => sum + (value - mean) ** 2, 0) / passRates.length;
}

/** S-R01/02/03：调用方必须显式提供阈值；三个维度属于同一规则族。 */
export function flagLowPlanQuality(score, threshold) {
  return unitValue(score, "score") < unitValue(threshold, "threshold");
}

/** S-R04/05/06：三阶段控制；不执行生成代码，不读取隐藏测试结果。 */
export function planCoderDecision(context) {
  if (!context || typeof context.publicPassed !== "boolean") throw new TypeError("publicPassed 必须是布尔值");
  const { publicPassed, planRepairs, codeRepairs, maxPlanRepairs = 5, maxCodeRepairs = 6 } = context;
  for (const value of [planRepairs, codeRepairs, maxPlanRepairs, maxCodeRepairs]) {
    if (!Number.isInteger(value) || value < 0) throw new TypeError("修复次数与上限必须是非负整数");
  }
  if (planRepairs > maxPlanRepairs || codeRepairs > maxCodeRepairs) throw new TypeError("修复次数超过配置上限");
  if (publicPassed) return "return_and_evaluate_hidden";
  if (planRepairs < maxPlanRepairs) return "repair_plan_and_regenerate_code";
  if (codeRepairs < maxCodeRepairs) return "retrieve_by_final_plan_and_repair_code";
  return "return_final_code_and_evaluate_hidden";
}

export function shouldRepairPlan(context) {
  return planCoderDecision(context) === "repair_plan_and_regenerate_code";
}

export function shouldRetrieveAndRepair(context) {
  return planCoderDecision(context) === "retrieve_by_final_plan_and_repair_code";
}

export function shouldStopPlanCoder(context) {
  return planCoderDecision(context).startsWith("return_");
}
