(async () => {
  try {
    const response = await fetch("./plancoder-evidence.json"); if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const datasets = ["mbpp-et", "apps", "codecontests", "livecodebench"];
    const table = document.getElementById("resultsTable"); table.textContent = "";
    for (const model of ["gpt-5.4-mini", "gpt-5.6-luna"]) {
      for (const method of ["plancoder", "mapcoder", "debatecoder", "lpw"]) {
        const row = document.createElement("tr"); const title = document.createElement("td"); title.textContent = `${model} / ${method}`; row.append(title);
        const results = datasets.map((dataset) => data.results.find((x) => x.model === model && x.method === method && x.dataset === dataset));
        for (const result of results) { const cell = document.createElement("td"); cell.textContent = result ? `${(100 * result.passAt1).toFixed(1)}%` : "缺少记录"; row.append(cell); }
        const average = document.createElement("td"); average.textContent = results.every(Boolean) ? `${(100 * results.reduce((sum, x) => sum + x.passAt1, 0) / 4).toFixed(1)}%` : "—"; row.append(average);
        if (method === "plancoder") row.style.fontWeight = "700"; table.append(row);
      }
    }
    document.getElementById("datasetCounts").textContent = "任务数：MBPP-ET 500 / APPS 139 / CodeContests 150 / LiveCodeBench 140；每个方法与模型组合共929题。";
    const issues = document.getElementById("evidenceIssues");
    for (const issue of data.issues) {
      const item = document.createElement("li");
      const label = { duplicate_tasks: "重复任务", merged_runs: "多次运行合并", zero_recorded_usage: "调用计量待核", missing_result: "缺少结果" }[issue.type] || issue.type;
      item.textContent = `${label}：${issue.source || issue.file}。${issue.resolution || "待补齐"}`; issues.append(item);
    }
    const pool = document.createElement("li"); pool.textContent = `检索池有 ${data.retrievalPool.items} 条记录。当前检索模型${data.retrievalPool.modelsPresentHere ? "目录存在，权重完整性仍需核验" : "目录缺失，完整生成实验需补齐模型"}。`; issues.append(pool);
  } catch (error) { document.getElementById("evidenceError").textContent = `证据索引加载失败：${error.message}`; }
})();
