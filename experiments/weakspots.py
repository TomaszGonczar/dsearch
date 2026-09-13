#!/usr/bin/env python3
"""Probe two weak spots in the design before building on it.

W1: Does the NO-CONSENSUS case actually occur? I designed a headline feature
    around overlap=0. If every query has some consensus, that feature is decoration.
W2: Is a provider stable across identical calls? If Brave returns different
    results each call, 'agreement' partly measures sampling noise, not index overlap.
"""
import os, sys
from concurrent.futures import ThreadPoolExecutor
exec(open(os.path.join(os.path.dirname(__file__), "overlap-probe.py")).read().split('def main()')[0])
keys = load_keys()

print("=" * 78)
print("W1 — does NO-CONSENSUS occur? Testing deliberately ambiguous/obscure queries")
print("=" * 78)
AMBIGUOUS = [
    "apple",                      # wildly ambiguous single word
    "mercury",                    # planet / element / company / mythology
    "model",                      # hopelessly overloaded
    "the best way",               # no referent
    "x",                          # degenerate
]
for q in AMBIGUOUS:
    results = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(fn, q, keys): name for name, fn in PROVIDERS.items()}
        for f, name in futs.items():
            try: results[name] = {canonicalize(u) for u in f.result()}
            except Exception: results[name] = set()
    names = [p for p in PROVIDERS if results.get(p)]
    all_urls = {}
    for p in names:
        for u in results[p]: all_urls.setdefault(u, []).append(p)
    cons = sum(1 for ps in all_urls.values() if len(ps) >= 2)
    union = len(all_urls)
    rate = cons/union if union else 0
    flag = "  <-- NO CONSENSUS" if cons == 0 else ""
    print(f"  {q!r:<20} union={union:>3} consensus={cons:>2} rate={rate:.3f}{flag}")

print()
print("=" * 78)
print("W2 — provider stability: same query 3x. Identical results = stable index.")
print("=" * 78)
q = "postgres index bloat monitoring"
for pname in ("brave", "exa", "tavily", "parallel"):
    runs = []
    for _ in range(3):
        try: runs.append({canonicalize(u) for u in PROVIDERS[pname](q, keys)})
        except Exception as e: runs.append(set())
    if not all(runs): print(f"  {pname}: error"); continue
    # Jaccard between run1 and each later run
    def jac(a,b): return len(a&b)/len(a|b) if (a|b) else 0
    j12, j13 = jac(runs[0],runs[1]), jac(runs[0],runs[2])
    verdict = "STABLE" if min(j12,j13) > 0.7 else "UNSTABLE — agreement partly measures noise"
    print(f"  {pname:<9} n={len(runs[0])} run1x2 J={j12:.2f} run1x3 J={j13:.2f}  {verdict}")
