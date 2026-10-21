const state = { data: null, kind: "metrics", query: "", status: "all", source: "all", type: "all", selected: { metrics: null, rules: null } };
const $ = (id) => document.getElementById(id);
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
const statusText = { A: "A · 实现与记录", B: "B · 待独立验证", C: "C · 机制候选" };

function entries() {
  return state.data?.[state.kind] ?? [];
}

function visibleEntries() {
  const search = state.query.trim().toLocaleLowerCase("zh-CN");
  return entries().filter((item) => {
    if (state.status !== "all" && item.status !== state.status) return false;
    if (state.source !== "all" && item.sourceKey !== state.source) return false;
    if (state.type !== "all" && item.entryType !== state.type) return false;
    if (!search) return true;
    return [item.id, item.name, item.group, item.summary, item.formula, item.condition, item.outcome, item.functionSignature, item.source, item.entryType]
      .filter(Boolean).join(" ").toLocaleLowerCase("zh-CN").includes(search);
  });
}

function detailBlock(label, content, extraClass = "") {
  return `<div class="detail-block ${extraClass}"><h4>${escapeHtml(label)}</h4><p>${escapeHtml(content)}</p></div>`;
}

function functionBlock(item, isMetric) {
  if (!item.functionSignature) return "";
  const functionName = item.functionSignature.split("(")[0];
  return `<div class="detail-block wide function-block"><h4>${isMetric ? "可复算函数" : item.entryType === "修复策略" ? "阶段控制函数" : "候选规则条件函数"}</h4>
    <code>${escapeHtml(item.functionSignature)}</code><p>${escapeHtml(item.functionNote)}</p>
    <a href="./functions.html?name=${encodeURIComponent(functionName)}" target="_blank" rel="noopener">查看函数定义 ↗</a></div>`;
}

function renderDetail(item) {
  const panel = $("detailPanel");
  if (!item) {
    panel.innerHTML = `<div class="empty-state">当前筛选下没有条目。试试其他关键词或状态。</div>`;
    return;
  }
  const isMetric = state.kind === "metrics";
  const highlightLabel = isMetric ? "计算口径" : item.entryType === "修复策略" ? "触发条件 → 执行动作" : "触发条件 → 风险提示";
  const highlight = isMetric ? item.formula : `${item.condition} → ${item.outcome}`;
  panel.innerHTML = `
    <div class="detail-kicker"><span>${escapeHtml(item.id)} / ${escapeHtml(item.group)} · ${escapeHtml(item.source)}</span><span class="status-pill status-${escapeHtml(item.status)}">${escapeHtml(statusText[item.status])}</span></div>
    <h3>${escapeHtml(item.name)}</h3>
    <p class="detail-summary">${escapeHtml(item.summary)}</p>
    <div class="detail-highlight"><small>${highlightLabel}</small><p>${escapeHtml(highlight)}</p></div>
    <div class="detail-grid">
      ${detailBlock("所需数据", item.inputs)}
      ${detailBlock(isMetric ? "适用范围" : item.entryType === "修复策略" ? "执行动作" : "风险输出", isMetric ? item.scope : item.outcome)}
      ${functionBlock(item, isMetric)}
      ${detailBlock("研究证据", item.evidence, "wide")}
      ${detailBlock("成果类型与计数", `${item.entryType}；${item.countingStatus}`, "wide")}
      <div class="detail-block wide"><h4>调用接口</h4><code>${escapeHtml(item.apiPath)}</code><p><a class="text-link" href="./api.html?id=${encodeURIComponent(item.id)}">查看请求示例与接口文档 ↗</a></p></div>
      ${detailBlock("当前限制", item.limits, "wide limit")}
      ${detailBlock("下一步核对", item.decision, "wide decision")}
    </div>
    ${item.inputExample ? `<section class="entry-demo"><h4>试算这个条目</h4><p>下方是可编辑的合成示例，用于检查函数行为，不是论文实验记录。预测阈值仅作演示。</p><label class="sr-only" for="demoInput">JSON 输入</label><textarea id="demoInput" rows="8" spellcheck="false">${escapeHtml(JSON.stringify(item.inputExample, null, 2))}</textarea><button type="button" id="runDemo" class="small-button">本地试算</button><pre id="demoOutput" aria-live="polite">点击“本地试算”查看结果。</pre></section>` : ""}`;
  if (item.inputExample) $("runDemo").addEventListener("click", async () => {
    try {
      const input = JSON.parse($("demoInput").value);
      const functions = await import("./catalog-functions.mjs");
      let value;
      if (["S-I01", "S-I02", "S-I03"].includes(item.id)) value = functions[item.functionSignature.split("(")[0]](input.review);
      else if (item.id === "S-I04") value = functions.planPassRateVariance(input.passRates);
      else if (["S-R01", "S-R02", "S-R03"].includes(item.id)) value = functions.flagLowPlanQuality(input.score, input.threshold);
      else value = { triggered: functions[item.functionSignature.split("(")[0]](input), action: functions.planCoderDecision(input) };
      $("demoOutput").textContent = JSON.stringify({ id: item.id, result: value, inputType: "用户提供或合成输入", interpretation: "不输出经过校准的失败概率" }, null, 2);
    } catch (error) { $("demoOutput").textContent = `输入错误：${error.message}`; }
  });
}

function render() {
  if (!state.data) return;
  const isMetric = state.kind === "metrics";
  $("metricTab").classList.toggle("is-active", isMetric);
  $("ruleTab").classList.toggle("is-active", !isMetric);
  $("metricTab").setAttribute("aria-selected", String(isMetric));
  $("ruleTab").setAttribute("aria-selected", String(!isMetric));
  $("catalogPanel").setAttribute("aria-labelledby", isMetric ? "metricTab" : "ruleTab");
  const typeOptions = [...new Set(entries().map((item) => item.entryType))];
  if (!typeOptions.includes(state.type)) state.type = "all";
  $("typeFilter").innerHTML = `<option value="all">全部成果类型</option>${typeOptions.map((type) => `<option value="${escapeHtml(type)}">${escapeHtml(type)}</option>`).join("")}`;
  $("typeFilter").value = state.type;
  $("resultLabel").textContent = isMetric ? "指标候选" : "规则候选";

  const list = visibleEntries();
  $("resultCount").textContent = `${list.length} 项`;
  if (!list.some((item) => item.id === state.selected[state.kind])) state.selected[state.kind] = list[0]?.id ?? null;

  $("entryList").innerHTML = list.length ? list.map((item) => `
    <button type="button" class="entry-card ${state.selected[state.kind] === item.id ? "is-selected" : ""}" data-entry-id="${escapeHtml(item.id)}" aria-pressed="${state.selected[state.kind] === item.id}">
      <span class="entry-topline"><span class="entry-id">${escapeHtml(item.id)}</span><span class="entry-group">${escapeHtml(item.group)}</span></span>
      <span class="entry-name-row"><strong>${escapeHtml(item.name)}</strong><span class="status-pill status-${escapeHtml(item.status)}">${escapeHtml(item.status)}</span></span>
      <p class="entry-source">${escapeHtml(item.sourceKey === "plancoder" ? "PlanCoder" : "PULSE")} · ${escapeHtml(item.entryType)}</p><p>${escapeHtml(item.summary)}</p>
    </button>`).join("") : `<div class="empty-state">没有匹配的条目。请调整搜索或筛选条件。</div>`;

  $("entryList").querySelectorAll("[data-entry-id]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selected[state.kind] = button.dataset.entryId;
      render();
      if (window.matchMedia("(max-width: 760px)").matches) $("detailPanel").scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
  renderDetail(list.find((item) => item.id === state.selected[state.kind]));
}

function bindControls() {
  document.querySelectorAll("[data-kind]").forEach((tab) => tab.addEventListener("click", () => {
    state.kind = tab.dataset.kind;
    state.query = "";
    state.status = "all";
    state.type = "all";
    $("searchInput").value = "";
    $("statusFilter").value = "all";
    render();
  }));
  $("searchInput").addEventListener("input", (event) => { state.query = event.target.value; render(); });
  $("statusFilter").addEventListener("change", (event) => { state.status = event.target.value; render(); });
  $("sourceFilter").addEventListener("change", (event) => { state.source = event.target.value; render(); });
  $("typeFilter").addEventListener("change", (event) => { state.type = event.target.value; render(); });
  document.querySelectorAll("[data-source]").forEach((button) => button.addEventListener("click", () => {
    state.source = button.dataset.source; state.type = "all"; state.query = ""; $("searchInput").value = "";
    $("sourceFilter").value = state.source; render(); $("catalog").scrollIntoView({ behavior: "smooth" });
  }));
  const tabs = [$("metricTab"), $("ruleTab")];
  tabs.forEach((tab, index) => tab.addEventListener("keydown", (event) => {
    if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
      event.preventDefault();
      tabs[1 - index].focus();
      tabs[1 - index].click();
    }
  }));
}

async function init() {
  bindControls();
  try {
    const response = await fetch("./catalog.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (!Array.isArray(data.metrics) || !Array.isArray(data.rules)) throw new Error("数据格式不完整");
    state.data = data;
    $("metricCount").textContent = data.metrics.length;
    $("ruleCount").textContent = data.rules.length;
    $("metricTabCount").textContent = String(data.metrics.length).padStart(2, "0");
    $("ruleTabCount").textContent = String(data.rules.length).padStart(2, "0");
    $("metricTarget").textContent = data.meta.contract.metrics;
    $("ruleTarget").textContent = data.meta.contract.rules;
    $("scopeText").textContent = data.meta.scope;
    $("headerDate").textContent = data.meta.asOf;
    $("footerDate").textContent = data.meta.asOf;
    render();
  } catch (error) {
    $("entryList").innerHTML = `<div class="empty-state">目录数据加载失败，请刷新页面重试。</div>`;
    $("detailPanel").innerHTML = `<div class="empty-state">无法读取条目详情。</div>`;
    console.error("Catalog load failed", error);
  }
}

init();
