const get = (id) => document.getElementById(id);
let apiEntries = [], available = false;
const examples = {
  "P-I01": { pairSimilarities: [0.8, 0.6, 0.7], implementationVersion: "synthetic-example-not-real-CodeBLEU" },
  "P-I02": { passRates: [0, 0.5, 1] }, "P-I03": { structuralDifference: 0.4, instability: 0.2 },
  "P-I04": { codes: ["return a + b", "return b + a"] }, "P-I05": { successes: [true, false, true] },
  "P-I06": { successes: [true, false, true] }, "P-I07": { codes: ["return a", "return a", "return b"] },
  "P-I08": { ambiguousUq: 0.5, clearUq: 0.2 }, "P-R01": { previousBatchUq: 0.7, threshold: 0.6 },
  "P-R02": { category: "vague" }, "P-R03": { category: "lexical" },
  "P-R04": { semanticGapDetected: true, uq: 0.2, lowUqThreshold: 0.3 },
  "P-R05": { checks: { premiseSupported: false, selfContained: true, entailed: true, historyConsistent: true, criticalConditionsComplete: true } },
  "P-R06": { uq: 0.2, lowUqThreshold: 0.3, criticalConstraintMissing: true }
};
function selectEntry() {
  const item = apiEntries.find((x) => x.id === get("apiEntry").value);
  get("apiDescription").textContent = `${item.entryType} · ${item.apiNote || item.summary}`;
  get("apiPath").textContent = `POST ${item.apiPath}`;
  get("apiInput").value = JSON.stringify(item.inputExample || examples[item.id] || {}, null, 2);
  get("curlExample").textContent = `curl -X POST ${location.origin}${item.apiPath} -H "Content-Type: application/json" --data '${JSON.stringify(item.inputExample || examples[item.id] || {})}'`;
}
async function post(path, input, output, button) {
  button.disabled = true;
  try {
    const data = JSON.parse(get(input).value);
    get(output).textContent = "正在请求…";
    const response = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
    const result = await response.json();
    get(output).textContent = `HTTP ${response.status}\n${JSON.stringify(result, null, 2)}`;
  } catch (error) { get(output).textContent = `请求失败：${error.message}`; }
  finally { button.disabled = false; }
}
(async () => {
  try {
    const response = await fetch("./catalog.json"); if (!response.ok) throw new Error("目录加载失败");
    const data = await response.json();
    apiEntries = [...data.metrics, ...data.rules];
    for (const item of apiEntries) { const option = document.createElement("option"); option.value = item.id; option.textContent = `${item.id} ${item.name}`; get("apiEntry").append(option); }
    const requested = new URLSearchParams(location.search).get("id");
    get("apiEntry").value = apiEntries.some((x) => x.id === requested) ? requested : "S-I04";
    selectEntry();
    get("apiEntry").addEventListener("change", selectEntry);
    get("apiRun").addEventListener("click", () => post(apiEntries.find((x) => x.id === get("apiEntry").value).apiPath, "apiInput", "apiOutput", get("apiRun")));
    get("judgeRun").addEventListener("click", () => post("/api/v1/plans/score", "judgeInput", "judgeOutput", get("judgeRun")));
    try {
      const healthResponse = await fetch("/api/v1/health"); if (!healthResponse.ok) throw new Error("API 未启动");
      const health = await healthResponse.json(); available = health.status === "ok";
      get("apiRun").disabled = !available;
      get("apiStatus").textContent = `本地 API 已连接 · 版本 ${health.version}`;
      get("judgeRun").disabled = !health.judgeAvailable;
      get("judgeStatus").textContent = health.judgeAvailable ? "模型评分已配置。提交前请确认当前输入可以发送给所配置的服务。" : "真实模型评分未配置；离线复算与规则接口可直接使用。";
    } catch (error) { get("apiStatus").textContent = "当前为静态预览。运行 python server.py 后即可调用 HTTP API。"; get("judgeStatus").textContent = "API 服务尚未连接。"; }
  } catch (error) { get("apiStatus").textContent = error.message; }
})();
