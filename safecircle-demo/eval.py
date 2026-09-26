"""
Run every sample through the detection engine and report accuracy.
Usage:  python eval.py          (rules only)
        python eval.py --ai     (rules + LLM, needs ANTHROPIC_API_KEY)
"""
import json
import os
import sys
import tempfile

os.environ.setdefault("SAFECIRCLE_DB", os.path.join(tempfile.mkdtemp(), "eval.db"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shield import engine, rules  # noqa: E402

use_ai = "--ai" in sys.argv
samples = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples.json"), encoding="utf-8"))

passed, missed_high = 0, 0
print(f"{'sample':22} {'expected':8} {'got':8} {'category':22} signals")
print("-" * 100)
for s in samples:
    r = engine.analyse(s["text"], use_ai=use_ai)
    ok = r["risk"] == s["expected"]
    passed += ok
    if s["expected"] == "high" and r["risk"] != "high":
        missed_high += 1
    shown = sorted(x for x in r["signals"] if x not in rules.INTERNAL_SIGNALS)
    print(f"{s['id']:22} {s['expected']:8} {r['risk']:8} {r['category']:22} {'' if ok else 'MISMATCH '}{', '.join(shown)}")

highs = sum(1 for s in samples if s["expected"] == "high")
print("-" * 100)
print(f"Exact match: {passed}/{len(samples)}   High-risk recall: {highs - missed_high}/{highs}   Mode: {'rules + AI' if use_ai else 'rules only'}")
