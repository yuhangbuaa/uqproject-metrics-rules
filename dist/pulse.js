const $ = (id) => document.getElementById(id);
const percentage = (value, places = 2) => `${value.toFixed(places)}%`;

function addCell(row, value) {
  const cell = document.createElement("td");
  cell.textContent = value;
  row.append(cell);
  return cell;
}

function renderDiagnostic(data) {
  const body = $("diagnosticRows");
  body.textContent = "";
  for (const item of data.rows) {
    const row = document.createElement("tr");
    addCell(row, item.condition);
    addCell(row, percentage(item.reliability));
    const barCell = addCell(row, "");
    const track = document.createElement("span"); track.className = "pulse-track";
    const bar = document.createElement("span"); bar.style.width = `${item.reliability}%`;
    track.append(bar); barCell.append(track);
    addCell(row, item.uq.toFixed(4));
    body.append(row);
  }
  $("diagnosticInterpretation").textContent = data.interpretation;
}

function renderPanel(data) {
  $("panelOriginal").textContent = percentage(data.originalReliability);
  $("panelClarified").textContent = percentage(data.clarifiedReliability);
  $("panelSplit").textContent = `${data.improved} / ${data.unchanged} / ${data.worsened}`;
  $("panelScope").textContent = `${data.selectedCases} 个分层案例、${data.arms} 组条件和 ${data.candidates.toLocaleString("zh-CN")} 个候选。${data.limitation}`;
}

function renderBudget(data) {
  $("budgetScope").textContent = `${data.baseTasks} 个基础任务构成 ${data.ambiguousCases} 个歧义案例，生成并评测 ${data.newCandidates.toLocaleString("zh-CN")} 个新候选。主预算在四种歧义条件中共澄清 ${data.mainClarifications} 次。`;
  const rows = [
    ["不澄清", data.noClarification, "基线"],
    ["全部澄清", data.allClarification, "观察到整体收益，同时存在退化案例"],
    ["高 UQ 优先", data.topUq, "同预算排序策略"],
    ["均匀随机期望", data.uniformRandomExpectation, "同预算精确期望"],
  ];
  const body = $("budgetRows"); body.textContent = "";
  for (const [name, value, note] of rows) {
    const row = document.createElement("tr");
    addCell(row, name); addCell(row, percentage(value, 4)); addCell(row, note); body.append(row);
  }
  const [low, high] = data.clusterCi95Pp;
  $("budgetInterpretation").textContent = `高 UQ 优先较随机期望高 ${data.differencePp.toFixed(4)} 个百分点，95% 任务聚类区间为 [${low.toFixed(4)}, +${high.toFixed(4)}] 个百分点，跨越零。${data.interpretation}`;
}

function renderSources(data) {
  const notes = $("pulseOpenItems"); notes.textContent = "";
  for (const note of data.openItems) {
    const item = document.createElement("li"); item.textContent = note; notes.append(item);
  }
  const sources = $("pulseSources"); sources.textContent = "";
  for (const source of data.sources) {
    const item = document.createElement("li");
    item.textContent = `${source.pathWithinUqclassifier} · SHA-256 ${source.sha256}`;
    sources.append(item);
  }
}

function renderDemo(catalog) {
  const entries = [...catalog.metrics, ...catalog.rules].filter((item) => item.sourceKey === "pulse");
  const select = $("pulseEntry"); select.textContent = "";
  for (const entry of entries) {
    const option = document.createElement("option"); option.value = entry.id;
    option.textContent = `${entry.id} ${entry.name}`; select.append(option);
  }
  const update = () => {
    const item = entries.find((entry) => entry.id === select.value);
    $("pulseEntryDescription").textContent = `${item.entryType} · ${item.summary}`;
    $("pulseInput").value = JSON.stringify(item.inputExample, null, 2);
    $("pulseOutput").textContent = "修改输入后点击“本地试算”。";
  };
  select.value = new URLSearchParams(location.search).get("id") || "P-I02";
  if (!entries.some((entry) => entry.id === select.value)) select.value = "P-I02";
  select.addEventListener("change", update);
  $("pulseRun").addEventListener("click", async () => {
    try {
      const input = JSON.parse($("pulseInput").value);
      const pulse = await import("./pulse-functions.mjs");
      const result = select.value.startsWith("P-I") ? pulse.evaluatePulseMetric(select.value, input) : pulse.evaluatePulseRule(select.value, input);
      $("pulseOutput").textContent = JSON.stringify({ id: select.value, result, inputType: "合成示例或用户输入", contractStatus: "候选条目，尚未核定独立计数" }, null, 2);
    } catch (error) { $("pulseOutput").textContent = `输入错误：${error.message}`; }
  });
  update();
}

(async () => {
  try {
    const [evidenceResponse, catalogResponse] = await Promise.all([fetch("./pulse-evidence.json"), fetch("./catalog.json")]);
    if (!evidenceResponse.ok || !catalogResponse.ok) throw new Error("数据文件未能加载");
    const [evidence, catalog] = await Promise.all([evidenceResponse.json(), catalogResponse.json()]);
    renderDiagnostic(evidence.diagnostic);
    renderPanel(evidence.panel);
    renderBudget(evidence.budget);
    renderSources(evidence);
    renderDemo(catalog);
  } catch (error) { $("pulseError").textContent = `PULSE 页面加载失败：${error.message}`; }
})();
