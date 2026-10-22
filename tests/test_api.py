import json
import io
import math
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plancoder_metrics import evaluate_metric, evaluate_rule, judge_prompt, repair_decision
from pulse_metrics import evaluate_metric as evaluate_pulse_metric, evaluate_rule as evaluate_pulse_rule
from server import Handler, ThreadingHTTPServer, score_plan


class MetricTests(unittest.TestCase):
    def test_population_variance(self):
        self.assertAlmostEqual(evaluate_metric("S-I04", {"passRates": [0, .5, 1, .5, .5]})["value"], .1)

    def test_stable_failure_has_zero_variance(self):
        self.assertEqual(evaluate_metric("S-I04", {"passRates": [0, 0, 0]})["value"], 0)

    def test_invalid_rates(self):
        for values in ([], [1], [True, 0], [float("nan"), 1], [float("inf"), 0], [-.1, .5], [1.1, 0]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                evaluate_metric("S-I04", {"passRates": values})

    def test_review_requires_provenance(self):
        with self.assertRaises(ValueError): evaluate_metric("S-I01", {"review": {"score": .8}})

    def test_review_dimension(self):
        for n, dimension in enumerate(("feasibility", "relevance", "clarity"), 1):
            result = evaluate_metric(f"S-I0{n}", {"review": {"dimension": dimension, "score": .8, "rationale": "有依据", "evaluator": "test-fixture", "rubricVersion": "1"}})
            self.assertEqual(result["value"], .8)
            self.assertIn("不是失败概率", result["interpretation"])

    def test_pulse_regression(self):
        self.assertAlmostEqual(evaluate_metric("P-I02", {"passRates": [0, .5, 1]})["value"], 2 / 3)
        self.assertEqual(evaluate_metric("P-I03", {"structuralDifference": .4, "instability": .2})["value"], .30000000000000004)
        self.assertEqual(evaluate_metric("P-I05", {"successes": [True, False]})["value"], 1)
        self.assertEqual(evaluate_metric("P-I06", {"successes": [True, False]})["value"], .25)


class RuleTests(unittest.TestCase):
    def test_threshold_is_explicit(self):
        with self.assertRaises(ValueError): evaluate_rule("S-R01", {"score": .2})

    def test_threshold_equality_does_not_trigger(self):
        self.assertFalse(evaluate_rule("S-R01", {"score": .6, "threshold": .6})["triggered"])
        self.assertTrue(evaluate_rule("S-R01", {"score": .59, "threshold": .6})["triggered"])

    def test_three_stages_and_exhaustion(self):
        cases = [(False, 0, 0, "repair_plan_and_regenerate_code"), (False, 5, 0, "retrieve_by_final_plan_and_repair_code"), (False, 5, 6, "return_final_code_and_evaluate_hidden"), (True, 0, 0, "return_and_evaluate_hidden")]
        for passed, plans, codes, action in cases:
            with self.subTest(action=action):
                result = repair_decision({"publicPassed": passed, "planRepairs": plans, "codeRepairs": codes})
                self.assertEqual(result["action"], action); self.assertEqual(result["maxCodeGenerations"], 12)

    def test_zero_budgets_and_invalid_counts(self):
        self.assertEqual(repair_decision({"publicPassed": False, "planRepairs": 0, "codeRepairs": 0, "maxPlanRepairs": 0, "maxCodeRepairs": 0})["action"], "return_final_code_and_evaluate_hidden")
        for field, value in (("planRepairs", True), ("planRepairs", -1), ("codeRepairs", 7), ("publicPassed", 1)):
            with self.subTest(field=field), self.assertRaises(ValueError):
                repair_decision({"publicPassed": False, "planRepairs": 0, "codeRepairs": 0, field: value})

    def test_strategy_not_prediction(self):
        self.assertEqual(evaluate_rule("S-R04", {"publicPassed": False, "planRepairs": 0, "codeRepairs": 0})["ruleType"], "修复策略")


class PulseLibraryTests(unittest.TestCase):
    def test_all_catalog_examples_have_callable_python_entries(self):
        catalog = json.loads((Path(__file__).resolve().parents[1] / "dist/catalog.json").read_text(encoding="utf-8"))
        for kind in ("metrics", "rules"):
            for item in catalog[kind]:
                if item["sourceKey"] != "pulse":
                    continue
                with self.subTest(identifier=item["id"]):
                    result = (evaluate_pulse_metric if kind == "metrics" else evaluate_pulse_rule)(item["id"], item["inputExample"])
                    self.assertIn("value" if kind == "metrics" else "triggered", result)

    def test_external_signals_and_thresholds_are_required(self):
        with self.assertRaises(ValueError): evaluate_pulse_metric("P-I01", {"pairSimilarities": [0.8]})
        with self.assertRaises(ValueError): evaluate_pulse_metric("P-I02", {"passRates": []})
        with self.assertRaises(ValueError): evaluate_pulse_rule("P-R04", {"semanticGapDetected": False, "uq": None, "lowUqThreshold": .3})
        with self.assertRaises(ValueError): evaluate_pulse_rule("P-R05", {"checks": {"premiseSupported": False}})
        with self.assertRaises(ValueError): evaluate_pulse_rule("P-R06", {"uq": .1, "lowUqThreshold": .3})


class JudgeTests(unittest.TestCase):
    def test_disabled_without_credentials(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(RuntimeError):
            score_plan({"problem": "求和", "plan": "相加", "visibleTests": ["assert add(1,2)==3"]})

    def test_relevance_and_clarity_do_not_receive_tests(self):
        for d in ("relevance", "clarity"):
            self.assertNotIn("SECRET_TEST_TOKEN", judge_prompt("p", "plan", ["SECRET_TEST_TOKEN"], [d]))
        self.assertIn("SECRET_TEST_TOKEN", judge_prompt("p", "plan", ["SECRET_TEST_TOKEN"], ["feasibility"]))

    def test_configured_judge_requests_are_separate(self):
        requests = []
        def fake_urlopen(request, timeout):
            payload = json.loads(request.data); requests.append(payload)
            content = payload["messages"][1]["content"]
            dimension = next(d for d in ("feasibility", "relevance", "clarity") if f"{d}: " in content)
            response = {"choices": [{"message": {"content": json.dumps({dimension: {"score": .7, "rationale": "synthetic test response"}})}}], "usage": {"total_tokens": 10}}
            return io.BytesIO(json.dumps(response).encode())
        with patch.dict(os.environ, {"PLAN_JUDGE_ENABLED": "1", "PLAN_JUDGE_API_KEY": "test-only-placeholder", "PLAN_JUDGE_MODEL": "test-fixture", "PLAN_JUDGE_BASE_URL": "https://example.com/v1"}), patch("server.urllib.request.urlopen", side_effect=fake_urlopen):
            result = score_plan({"problem": "p", "plan": "plan", "visibleTests": ["SECRET_TEST_TOKEN"]})
        self.assertEqual(result["usage"], {"llm_calls": 3, "total_tokens": 30})
        self.assertEqual(len(requests), 3)
        self.assertNotIn("SECRET_TEST_TOKEN", requests[1]["messages"][1]["content"])
        self.assertNotIn("SECRET_TEST_TOKEN", requests[2]["messages"][1]["content"])

    def test_invalid_model_score_rejected(self):
        response = {"choices": [{"message": {"content": '{"feasibility":{"score":2,"rationale":"invalid synthetic response"}}'}}]}
        with patch.dict(os.environ, {"PLAN_JUDGE_ENABLED": "1", "PLAN_JUDGE_API_KEY": "test-only-placeholder", "PLAN_JUDGE_MODEL": "test-fixture", "PLAN_JUDGE_BASE_URL": "https://example.com/v1"}), patch("server.urllib.request.urlopen", return_value=io.BytesIO(json.dumps(response).encode())), self.assertRaises(ValueError):
            score_plan({"problem": "p", "plan": "plan", "visibleTests": ["test"], "dimensions": ["feasibility"]})


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(timeout=3)

    def call(self, path, data=None, headers=None, raw=None):
        body = raw if raw is not None else (json.dumps(data).encode() if data is not None else None)
        request = urllib.request.Request(self.base + path, data=body, headers=headers or ({"Content-Type": "application/json"} if body else {}))
        try: response = urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as error: response = error
        with response: return response.status, json.load(response)

    def test_health(self): self.assertEqual(self.call("/api/v1/health")[1]["status"], "ok")

    def test_source_filter_preserves_pulse(self):
        self.assertEqual(self.call("/api/v1/metrics?sourceKey=plancoder")[1]["count"], 4)
        self.assertEqual(self.call("/api/v1/metrics?sourceKey=pulse")[1]["count"], 8)
        self.assertEqual(self.call("/api/v1/rules?sourceKey=plancoder")[1]["count"], 6)

    def test_compute_endpoint(self):
        status, result = self.call("/api/v1/metrics/S-I04/evaluate", {"passRates": [0, 1]})
        self.assertEqual(status, 200); self.assertEqual(result["result"]["value"], .25)

    def test_invalid_input_and_json(self):
        self.assertEqual(self.call("/api/v1/metrics/S-I04/evaluate", {"passRates": [2, 0]})[0], 400)
        self.assertEqual(self.call("/api/v1/metrics/S-I04/evaluate", raw=b'{"passRates":[NaN,0]}', headers={"Content-Type": "application/json"})[0], 400)

    def test_unknown_identifier(self): self.assertEqual(self.call("/api/v1/metrics/S-I99/evaluate", {})[0], 404)

    def test_content_type(self): self.assertEqual(self.call("/api/v1/plans/decision", raw=b"{}", headers={"Content-Type": "text/plain"})[0], 415)

    def test_cross_origin(self): self.assertEqual(self.call("/api/v1/plans/decision", {}, headers={"Content-Type": "application/json", "Origin": "https://example.com"})[0], 403)

    def test_openapi_and_evidence(self):
        self.assertEqual(self.call("/api/v1/openapi.json")[1]["openapi"], "3.1.0")
        self.assertEqual(len(self.call("/api/v1/evidence")[1]["results"]), 32)
        self.assertEqual(self.call("/api/v1/pulse/evidence")[1]["budget"]["ambiguousCases"], 520)

    def test_pulse_entry_endpoints_use_the_standalone_library(self):
        status, result = self.call("/api/v1/metrics/P-I02/evaluate", {"passRates": [0, .5, 1]})
        self.assertEqual(status, 200)
        self.assertAlmostEqual(result["result"]["value"], 2 / 3)
        status, result = self.call("/api/v1/rules/P-R04/evaluate", {"semanticGapDetected": True, "uq": .2, "lowUqThreshold": .3})
        self.assertEqual(status, 200)
        self.assertTrue(result["result"]["triggered"])

    def test_pulse_page_and_module_are_served(self):
        for path, expected in (("/pulse.html", "PULSE 需求端不确定性感知"),
                               ("/pulse-functions.mjs", "evaluatePulseMetric"),
                               ("/pulse-evidence.json", "clusterCi95Pp")):
            with self.subTest(path=path), urllib.request.urlopen(self.base + path, timeout=5) as response:
                self.assertEqual(response.status, 200)
                self.assertIn(expected, response.read().decode("utf-8"))

    def test_judge_disabled_status(self):
        with patch.dict(os.environ, {"PLAN_JUDGE_ENABLED": "0"}):
            self.assertEqual(self.call("/api/v1/plans/score", {"problem": "p", "plan": "plan", "visibleTests": ["test"]})[0], 503)


if __name__ == "__main__": unittest.main(verbosity=2)
