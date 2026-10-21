"""执行可复算的本地检查并保存真实测试结果，不调用外部模型。"""
import argparse
import datetime
import hashlib
import io
import json
import os
import platform
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
parser = argparse.ArgumentParser(); parser.add_argument("--node", required=True); args = parser.parse_args()
stream = io.StringIO()
suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
node = subprocess.run([args.node, "--test", "--test-reporter=tap", str(ROOT / "tests/catalog-functions.test.mjs")], cwd=ROOT, text=True, encoding="utf-8", capture_output=True)
node_tests = int(re.search(r"# tests (\d+)", node.stdout).group(1))
evidence = {"executedAt": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(), "scope": "本机内部自测，非专家或第三方测试", "externalModelCalled": False,
    "python": {"version": platform.python_version(), "tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "passed": result.wasSuccessful()},
    "javascript": {"version": subprocess.check_output([args.node, "--version"], text=True).strip(), "tests": node_tests, "passed": node.returncode == 0},
    "environment": {"system": platform.system(), "release": platform.release(), "machine": platform.machine(), "processor": platform.processor()},
    "catalog": {"metrics": 12, "rules": 12, "plancoderMetrics": 4, "plancoderRiskHypotheses": 3, "plancoderStrategies": 3},
    "sourceHashes": {str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT / "server.py", ROOT / "plancoder_metrics.py", ROOT / "dist/catalog-functions.mjs", ROOT / "dist/catalog.json", ROOT / "tests/test_api.py", ROOT / "tests/catalog-functions.test.mjs"]}}
work = ROOT / ".work/midterm"; work.mkdir(parents=True, exist_ok=True)
(work / "python-tests.txt").write_text(stream.getvalue(), encoding="utf-8")
(work / "javascript-tests.txt").write_text(node.stdout + node.stderr, encoding="utf-8")
(ROOT / "dist/selftest-results.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"pythonPassed": result.wasSuccessful(), "pythonTests": result.testsRun, "javascriptPassed": node.returncode == 0, "javascriptTests": node_tests}, ensure_ascii=False))
sys.exit(0 if result.wasSuccessful() and node.returncode == 0 else 1)
