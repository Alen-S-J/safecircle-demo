"""
Run every sample through the detection engine and report accuracy.
Usage:  python eval.py          (rules only)
        python eval.py --ai     (rules + LLM, needs OPENAI_API_KEY)
        python eval.py --ml     (rules + ML stack if models/ present)
"""
import json
import os
import sys
import tempfile

os.environ.setdefault("SAFECIRCLE_DB", os.path.join(tempfile.mkdtemp(), "eval.db"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shield import engine, rules  # noqa: E402
from shield import ml_layer  # noqa: E402

use_ai = "--ai" in sys.argv
use_ml = "--ml" in sys.argv
samples = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples.json"), encoding="utf-8"))

passed, missed_high = 0, 0
print(f"{'sample':22} {'expected':8} {'got':8} {'sev':8} {'p_ml':6} {'category':22} signals")
print("-" * 110)
for s in samples:
    if use_ml:
        r = engine.check(s["text"], lang=s.get("lang", "en"), use_ai=use_ai)
        risk = r["risk"]
        sev = r.get("severity", "")
        p_ml = (r.get("ml") or {}).get("scam_probability")
        cat = r["category"]
        sigs = set(r["signals"])
    else:
        r = engine.analyse(s["text"], use_ai=use_ai)
        risk = r["risk"]
        sev = r.get("severity", "")
        p_ml = None
        if use_ml:
            ml = ml_layer.predict(s["text"])
            p_ml = ml["scam_probability"] if ml else None
        cat = r["category"]
        sigs = r["signals"]
    ok = risk == s["expected"]
    passed += ok
    if s["expected"] == "high" and risk != "high":
        missed_high += 1
    shown = sorted(x for x in sigs if x not in rules.INTERNAL_SIGNALS)
    pstr = f"{p_ml:.2f}" if p_ml is not None else "  -  "
    print(f"{s['id']:22} {s['expected']:8} {risk:8} {sev:8} {pstr:6} {cat:22} {'' if ok else 'MISMATCH '}{', '.join(shown)}")

highs = sum(1 for s in samples if s["expected"] == "high")
print("-" * 110)
mode = "rules only"
if use_ai and use_ml:
    mode = "rules + AI + ML"
elif use_ai:
    mode = "rules + AI"
elif use_ml:
    mode = "rules + ML"
print(f"Exact match: {passed}/{len(samples)}   High-risk recall: {highs - missed_high}/{highs}   Mode: {mode}")
print(f"ML available: {ml_layer.available()}")
