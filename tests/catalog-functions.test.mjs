import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as f from '../dist/catalog-functions.mjs';
import * as pulse from '../dist/pulse-functions.mjs';

const modelOptions = {
  apiKey: 'test-only-api-key', baseUrl: 'https://judge.example/v1/', model: 'test-judge',
  problem: '返回两个数之和', plan: '相加并返回'
};
const modelResponse = (dimension, score = .73, rationale = 'synthetic model response') => new Response(JSON.stringify({
  choices: [{ message: { content: JSON.stringify({ [dimension]: { score, rationale } }) } }],
  usage: { total_tokens: 25 }
}), { status: 200 });

test('Three callable scoring functions request their dimension and return model scores with provenance', async t => {
  const requests = [];
  t.mock.method(globalThis, 'fetch', async (url, request) => {
    requests.push({ url, request });
    const content = JSON.parse(request.body).messages[1].content;
    const dimension = ['feasibility', 'relevance', 'clarity'].find(d => content.includes(`${d}: `));
    return modelResponse(dimension);
  });
  for (const [name, dimension] of [['planFeasibility', 'feasibility'], ['planRelevance', 'relevance'], ['planClarity', 'clarity']]) {
    const result = await f[name]({ ...modelOptions, visibleTests: ['VISIBLE_TEST_TOKEN'] });
    assert.equal(result.value, .73);
    assert.equal(result.dimension, dimension);
    assert.equal(result.rationale, 'synthetic model response');
    assert.equal(result.evaluator, 'test-judge');
    assert.equal(result.rubricVersion, 'plancoder-plan-quality-1.0');
    assert.deepEqual(result.usage, { llm_calls: 1, total_tokens: 25 });
    assert.ok(!JSON.stringify(result).includes(modelOptions.apiKey));
  }
  assert.equal(requests.length, 3);
  for (const { url, request } of requests) {
    assert.equal(url, 'https://judge.example/v1/chat/completions');
    assert.equal(request.headers.Authorization, `Bearer ${modelOptions.apiKey}`);
    assert.equal(request.redirect, 'error');
    assert.ok(!request.body.includes(modelOptions.apiKey));
    assert.equal(JSON.parse(request.body).model, 'test-judge');
  }
  assert.ok(requests[0].request.body.includes('VISIBLE_TEST_TOKEN'));
  assert.ok(!requests[1].request.body.includes('VISIBLE_TEST_TOKEN'));
  assert.ok(!requests[2].request.body.includes('VISIBLE_TEST_TOKEN'));
});
test('Invalid scoring inputs are rejected before requesting a model', async t => {
  const fetchMock = t.mock.method(globalThis, 'fetch', async () => { throw new Error('must not call'); });
  await assert.rejects(f.planRelevance(), /apiKey/);
  await assert.rejects(f.planRelevance({ ...modelOptions, review: { score: .8 }, apiKey: '' }), /apiKey/);
  for (const patch of [{ model: '' }, { problem: '' }, { plan: ' ' }, { plan: 'x'.repeat(30001) }, { timeoutMs: 0 }, { timeoutMs: Infinity }]) {
    await assert.rejects(f.planRelevance({ ...modelOptions, ...patch }));
  }
  for (const baseUrl of ['', 'http://judge.example/v1', 'invalid-url', 'https://user:pass@judge.example/v1', 'https://judge.example/v1?key=secret']) {
    await assert.rejects(f.planClarity({ ...modelOptions, baseUrl }), /baseUrl/);
  }
  for (const visibleTests of [undefined, [], [''], [1], 'test']) {
    await assert.rejects(f.planFeasibility({ ...modelOptions, visibleTests }), /visibleTests/);
  }
  assert.equal(fetchMock.mock.callCount(), 0);
});
test('Invalid model scores and missing reasons are rejected', async t => {
  const mock = t.mock.method(globalThis, 'fetch');
  for (const score of [-.1, 1.1, '0.8', null, true]) {
    mock.mock.mockImplementation(async () => modelResponse('clarity', score));
    await assert.rejects(f.planClarity(modelOptions), /review.score/);
  }
  mock.mock.mockImplementation(async () => modelResponse('clarity', .8, ''));
  await assert.rejects(f.planClarity(modelOptions), /review.rationale/);
});
test('Malformed model responses fail without returning a fabricated score', async t => {
  const mock = t.mock.method(globalThis, 'fetch');
  for (const raw of ['not-json', '{}', JSON.stringify({ choices: [{ message: { content: 'not-json' } }] })]) {
    mock.mock.mockImplementation(async () => new Response(raw));
    await assert.rejects(f.planRelevance(modelOptions), /模型返回格式无效/);
  }
  mock.mock.mockImplementation(async () => modelResponse('clarity'));
  await assert.rejects(f.planRelevance(modelOptions));
});
test('HTTP and network errors do not expose the caller API key', async t => {
  const mock = t.mock.method(globalThis, 'fetch', async () => new Response(modelOptions.apiKey, { status: 401 }));
  await assert.rejects(f.planRelevance(modelOptions), error => error.message.includes('401') && !error.message.includes(modelOptions.apiKey));
  mock.mock.mockImplementation(async () => { throw new Error(modelOptions.apiKey); });
  await assert.rejects(f.planClarity(modelOptions), error => error.message.includes('模型服务请求失败') && !error.message.includes(modelOptions.apiKey));
});
test('Timeout aborts the model request', async t => {
  t.mock.method(globalThis, 'fetch', (_url, request) => new Promise((_resolve, reject) => {
    request.signal.addEventListener('abort', () => reject(new Error('aborted')), { once: true });
  }));
  await assert.rejects(f.planRelevance({ ...modelOptions, timeoutMs: 5 }), /超时/);
});
test('Fenced model JSON and absent token usage remain supported', async t => {
  t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify({
    choices: [{ message: { content: '```json\n{"clarity":{"score":0.4,"rationale":"synthetic"}}\n```' } }]
  })));
  const result = await f.planClarity(modelOptions);
  assert.equal(result.value, .4);
  assert.deepEqual(result.usage, { llm_calls: 1, total_tokens: 0 });
});
test('Population variance and stable failure boundary', () => {
  assert.equal(f.planPassRateVariance([0, .5, 1, .5, .5]), .1);
  assert.equal(f.planPassRateVariance([0, 0]), 0);
  for (const input of [[], [1], [NaN, 0], [Infinity, 0], [true, 0], [-1, 0]]) assert.throws(() => f.planPassRateVariance(input));
});
test('Explicit risk threshold and strict boundary', () => {
  assert.equal(f.flagLowPlanQuality(.6, .6), false);
  assert.equal(f.flagLowPlanQuality(.59, .6), true);
  assert.throws(() => f.flagLowPlanQuality(.4));
});
test('PlanCoder stage transitions and generation budget', () => {
  const base = { publicPassed: false, planRepairs: 0, codeRepairs: 0 };
  assert.equal(f.shouldRepairPlan(base), true);
  assert.equal(f.shouldRetrieveAndRepair({ ...base, planRepairs: 5 }), true);
  assert.equal(f.shouldStopPlanCoder({ ...base, planRepairs: 5, codeRepairs: 6 }), true);
  assert.equal(f.planCoderDecision({ ...base, publicPassed: true }), 'return_and_evaluate_hidden');
  assert.throws(() => f.planCoderDecision({ ...base, planRepairs: -1 }));
  assert.throws(() => f.planCoderDecision({ ...base, codeRepairs: 7 }));
});
test('Existing PULSE calculations remain available', () => {
  assert.ok(Math.abs(f.assertionPassInstability([0, .5, 1]) - 2 / 3) < 1e-12);
  assert.equal(f.outcomeEntropy([true, false]), 1);
  assert.equal(f.outcomeVariance([true, false]), .25);
  assert.equal(f.uniqueCodeRatio(['a', 'a', 'b']), 2 / 3);
  assert.equal(f.flagHighUq(.7, .6), true);
});
test('Standalone PULSE module evaluates every catalog entry with object input', () => {
  const catalog = JSON.parse(readFileSync(new URL('../dist/catalog.json', import.meta.url), 'utf8'));
  for (const kind of ['metrics', 'rules']) {
    for (const entry of catalog[kind].filter(item => item.sourceKey === 'pulse')) {
      const result = kind === 'metrics' ? pulse.evaluatePulseMetric(entry.id, entry.inputExample) : pulse.evaluatePulseRule(entry.id, entry.inputExample);
      assert.equal(typeof result[kind === 'metrics' ? 'value' : 'triggered'], kind === 'metrics' ? 'number' : 'boolean', entry.id);
    }
  }
  assert.throws(() => pulse.evaluatePulseMetric('P-I01', { pairSimilarities: [.8] }), /implementationVersion/);
  assert.throws(() => pulse.evaluatePulseMetric('P-I02', { passRates: [] }), /非空/);
  assert.throws(() => pulse.evaluatePulseRule('P-R04', { semanticGapDetected: false, uq: null, lowUqThreshold: .3 }), /uq/);
});
test('Every catalog function signature points to an exported function', () => {
  const catalog = JSON.parse(readFileSync(new URL('../dist/catalog.json', import.meta.url), 'utf8'));
  for (const entry of [...catalog.metrics, ...catalog.rules]) assert.equal(typeof f[entry.functionSignature.split('(')[0]], 'function', entry.id);
  assert.equal(catalog.metrics.length, 12); assert.equal(catalog.rules.length, 12);
  assert.equal(catalog.rules.filter(x => x.entryType === '修复策略').length, 3);
  const quality = catalog.metrics.filter(x => ['S-I01', 'S-I02', 'S-I03'].includes(x.id));
  for (const entry of quality) {
    assert.equal(entry.functionExecution, 'model');
    assert.ok(entry.functionSignature.includes('apiKey'));
    assert.ok(entry.functionExample.includes('await '));
    assert.ok(entry.functionReturns.includes('rationale'));
    assert.ok(entry.apiNote.includes('review'));
  }
});
