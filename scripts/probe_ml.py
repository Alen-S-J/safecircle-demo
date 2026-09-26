import json
import os
os.environ.setdefault("SAFECIRCLE_ML_DEVICE", "cpu")
from shield import ml_layer
ml_layer.warmup()
samples = json.load(open("samples.json", encoding="utf-8"))
for s in samples:
    r = ml_layer.predict(s["text"])
    print(f"{s['expected']:6} p={r['scam_probability']:.3f}  {s['id']}")
print("status", ml_layer.status())
