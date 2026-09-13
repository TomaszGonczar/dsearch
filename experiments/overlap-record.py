#!/usr/bin/env python3
"""Record raw overlap data to JSON for the evidence trail, and compute the
numbers that actually drive design decisions."""
import json, os, sys, datetime
sys.path.insert(0, os.path.dirname(__file__))
from importlib import import_module
probe = import_module("overlap-probe") if False else None
exec(open(os.path.join(os.path.dirname(__file__), "overlap-probe.py")).read().split('def main()')[0])

QUERIES = [
    "vercel.json schema validation",
    "python 3.13 free-threading status",
    "postgres index bloat monitoring",
    "RFC 9110 conditional requests",
    "rust tokio cancellation safety",
    "kubernetes pod disruption budget",
]
keys = load_keys()
from concurrent.futures import ThreadPoolExecutor

record = {"measured_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "providers": [p for p in PROVIDERS if p.upper()+"_API_KEY" in keys],
          "queries": []}

for q in QUERIES:
    results = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(fn, q, keys): name for name, fn in PROVIDERS.items()}
        for f, name in futs.items():
            try: results[name] = {canonicalize(u) for u in f.result()}
            except Exception: results[name] = set()
    names = [p for p in PROVIDERS if results.get(p)]
    # consensus = URL surfaced by >=2 providers
    all_urls = {}
    for p in names:
        for u in results[p]:
            all_urls.setdefault(u, []).append(p)
    consensus = {u: ps for u, ps in all_urls.items() if len(ps) >= 2}
    union = len(all_urls)
    rec = {
        "query": q,
        "per_provider": {p: len(results[p]) for p in names},
        "union": union,
        "consensus": len(consensus),
        "consensus_rate": round(len(consensus)/union, 4) if union else 0,
        # how much of a SINGLE provider's list is unique to it?
        "unique_share": {p: round(sum(1 for u in results[p] if len(all_urls[u])==1)/max(1,len(results[p])),4)
                         for p in names},
    }
    record["queries"].append(rec)
    print(f"{q[:34]:<36} union={union:>3} consensus={len(consensus):>2} "
          f"rate={rec['consensus_rate']:.3f}  unique: " +
          " ".join(f"{p[:3]}={rec['unique_share'][p]:.2f}" for p in names))

# aggregate
tot_union = sum(q["union"] for q in record["queries"])
tot_cons  = sum(q["consensus"] for q in record["queries"])
record["aggregate"] = {
    "queries": len(record["queries"]),
    "total_union": tot_union,
    "total_consensus": tot_cons,
    "mean_consensus_rate": round(tot_cons/tot_union, 4) if tot_union else 0,
    "mean_unique_share": {
        p: round(sum(q["unique_share"][p] for q in record["queries"] if p in q["unique_share"]) /
                 max(1, sum(1 for q in record["queries"] if p in q["unique_share"])), 4)
        for p in record["providers"]},
}
print()
print("AGGREGATE:", json.dumps(record["aggregate"], indent=1))

os.makedirs("experiments/data", exist_ok=True)
out = "experiments/data/overlap-2026-09-13.json"
json.dump(record, open(out, "w"), indent=2)
print(f"\nwritten: {out}")
