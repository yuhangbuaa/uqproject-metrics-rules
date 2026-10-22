/**
 * PULSE 需求端候选指标与风险条件函数。
 * 调用方提供代码生成、测试、需求分类及澄清审核结果。
 * 函数在本地计算；本模块不读取研究仓库或连接数据库。
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
  if (!passRates.length) throw new TypeError("passRates 必须是非空数组");
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
  if (!codes.length) throw new TypeError("codes 必须是非空数组");
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
  if (!successes.length) throw new TypeError("successes 必须是非空数组");
  const p = successes.filter(Boolean).length / successes.length;
  return p === 0 || p === 1 ? 0 : -p * Math.log2(p) - (1 - p) * Math.log2(1 - p);
}

/** P-I06：与 P-I05 使用同一个 p，独立计数待核。 */
export function outcomeVariance(successes) {
  booleans(successes, "successes");
  if (!successes.length) throw new TypeError("successes 必须是非空数组");
  const p = successes.filter(Boolean).length / successes.length;
  return p * (1 - p);
}

/** P-I07：按代码字符串完全一致判断重复。 */
export function uniqueCodeRatio(codes) {
  strings(codes, "codes");
  if (!codes.length) throw new TypeError("codes 必须是非空数组");
  return new Set(codes).size / codes.length;
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
  const value = unitValue(uq, "uq");
  const threshold = unitValue(lowUqThreshold, "lowUqThreshold");
  return semanticGapDetected && value <= threshold;
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

/** 与 HTTP API 使用相同的对象输入，便于按条目编号调用和复核。 */
export function evaluatePulseMetric(identifier, input) {
  if (!input || typeof input !== "object" || Array.isArray(input)) throw new TypeError("input 必须是对象");
  switch (identifier) {
    case "P-I01": {
      const scores = numbersInUnitInterval(input.pairSimilarities, "pairSimilarities");
      if (!scores.length) throw new TypeError("pairSimilarities 必须是非空数组");
      if (typeof input.implementationVersion !== "string" || !input.implementationVersion.trim()) {
        throw new TypeError("需提供外部 CodeBLEU implementationVersion");
      }
      return { value: 1 - scores.reduce((sum, value) => sum + value, 0) / scores.length,
        implementationVersion: input.implementationVersion,
        interpretation: "聚合外部提供的全部两两相似度；本模块不运行 CodeBLEU" };
    }
    case "P-I02": return { value: assertionPassInstability(input.passRates) };
    case "P-I03": return { value: pulseUq(input.structuralDifference, input.instability) };
    case "P-I04": return { value: lineJaccardDiversity(input.codes) };
    case "P-I05": return { value: outcomeEntropy(input.successes) };
    case "P-I06": return { value: outcomeVariance(input.successes) };
    case "P-I07": return { value: uniqueCodeRatio(input.codes) };
    case "P-I08": return { value: pairedUqDelta(input.ambiguousUq, input.clearUq) };
    default: throw new RangeError(`未知 PULSE 指标：${identifier}`);
  }
}

/** 返回候选条件是否触发；分类、语义缺口和回答核对由调用方提供。 */
export function evaluatePulseRule(identifier, input) {
  if (!input || typeof input !== "object" || Array.isArray(input)) throw new TypeError("input 必须是对象");
  let triggered;
  switch (identifier) {
    case "P-R01": triggered = flagHighUq(input.previousBatchUq, input.threshold); break;
    case "P-R02": triggered = flagAmbiguityCategory(input.category, "vague"); break;
    case "P-R03": triggered = flagAmbiguityCategory(input.category, "lexical"); break;
    case "P-R04": triggered = flagSemanticRisk(input.semanticGapDetected, input.uq, input.lowUqThreshold); break;
    case "P-R05": triggered = flagUnsupportedClarification(input.checks); break;
    case "P-R06": triggered = flagStableMisunderstanding(input.uq, input.lowUqThreshold, input.criticalConstraintMissing); break;
    default: throw new RangeError(`未知 PULSE 规则：${identifier}`);
  }
  return { triggered, ruleType: "候选风险条件", validatedThreshold: false,
    interpretation: "仅判断条件；外部识别信号及阈值须另行验证，不输出失败概率" };
}
