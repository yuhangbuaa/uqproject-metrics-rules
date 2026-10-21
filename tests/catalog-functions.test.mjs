import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as f from '../dist/catalog-functions.mjs';

test('PlanCoder quality reviews retain input provenance requirements', () => {
  const review = { dimension: 'feasibility', score: .8, rationale: 'synthetic', evaluator: 'test', rubricVersion: '1' };
  assert.equal(f.planFeasibility(review), .8);
  assert.throws(() => f.planRelevance(review));
  assert.throws(() => f.planClarity({ score: .8 }));
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
test('Every catalog function signature points to an exported function', () => {
  const catalog = JSON.parse(readFileSync(new URL('../dist/catalog.json', import.meta.url), 'utf8'));
  for (const entry of [...catalog.metrics, ...catalog.rules]) assert.equal(typeof f[entry.functionSignature.split('(')[0]], 'function', entry.id);
  assert.equal(catalog.metrics.length, 12); assert.equal(catalog.rules.length, 12);
  assert.equal(catalog.rules.filter(x => x.entryType === '修复策略').length, 3);
});
