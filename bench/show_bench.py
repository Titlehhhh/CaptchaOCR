import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import results

d = json.load(open(results("bench_results.json"), encoding='utf-8'))
for k, v in d.items():
    if v.get('ok'):
        print(f"{k}: acc={v.get('accuracy')} cer={v.get('mean_cer')} "
              f"{v.get('exact')}/{v.get('n')} t={v.get('seconds')}s")
    else:
        print(f"{k}: FAIL {str(v.get('error',''))[:160]}")

print("\n--- per-model sample predictions ---")
for k, v in d.items():
    if v.get('ok') and v.get('preds'):
        print(f"\n## {k}  (acc={v.get('accuracy')}, cer={v.get('mean_cer')})")
        seen = set()
        for p in v['preds']:
            if p['type'] in seen:
                continue
            seen.add(p['type'])
            print(f"   {p['type']}: gold={p['gold']!r} pred={p['pred_norm']!r} cer={p['cer']}")