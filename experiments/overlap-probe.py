#!/usr/bin/env python3
"""Measure real overlap between search providers.

This tests the load-bearing assumption of the product: that independent indexes
disagree often enough for the consensus signal to carry information.

If overlap is ~100%, they share an upstream and consensus is theatre.
If overlap is ~0%, they never agree and consensus never fires.
The useful middle is where this product lives.

Read-only. No writes outside stdout. Reads keys from Omega-v3/.env.
"""
import json, os, re, sys, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

ENV_PATH = os.path.expanduser("~/Omega-v3/.env")
TIMEOUT = 20.0

def load_keys():
    keys = {}
    for line in open(ENV_PATH):
        m = re.match(r"^([A-Z0-9_]+)=(.*)$", line.strip())
        if m:
            keys[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return keys

def canonicalize(url: str) -> str:
    """Strip tracking params, normalize host/scheme. Agreement must be on the PAGE,
    not on vendor URL decoration — without this, three engines returning the same
    page look like three different results."""
    TRACKING = {"utm_source","utm_medium","utm_campaign","utm_term","utm_content",
                "fbclid","gclid","msclkid","ref","source","mc_cid","mc_eid"}
    try:
        p = urllib.parse.urlparse(url.strip())
        netloc = p.netloc.lower().removeprefix("www.")
        if p.query:
            q = urllib.parse.parse_qsl(p.query, keep_blank_values=False)
            q = [(k, v) for k, v in q if k.lower() not in TRACKING]
            qs = urllib.parse.urlencode(q)
        else:
            qs = ""
        return urllib.parse.urlunparse((p.scheme.lower() or "https", netloc,
                                        p.path.rstrip("/"), "", qs, ""))
    except Exception:
        return url.strip().rstrip("/")

def post(url, body, headers):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode())

def get(url, headers):
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode())

def search_brave(q, keys, n=10):
    params = urllib.parse.urlencode({"q": q, "count": n})
    d = get(f"https://api.search.brave.com/res/v1/web/search?{params}",
            {"X-Subscription-Token": keys["BRAVE_API_KEY"],
             "Accept": "application/json"})
    return [i["url"] for i in (d.get("web", {}).get("results") or []) if i.get("url")]

def search_exa(q, keys, n=10):
    d = post("https://api.exa.ai/search",
             {"query": q, "numResults": n, "type": "auto"},
             {"x-api-key": keys["EXA_API_KEY"], "Content-Type": "application/json"})
    return [i["url"] for i in (d.get("results") or []) if i.get("url")]

def search_tavily(q, keys, n=10):
    d = post("https://api.tavily.com/search",
             {"query": q, "max_results": n, "search_depth": "basic"},
             {"Authorization": f"Bearer {keys['TAVILY_API_KEY']}",
              "Content-Type": "application/json"})
    return [i["url"] for i in (d.get("results") or []) if i.get("url")]

def search_parallel(q, keys, n=10):
    d = post("https://api.parallel.ai/v1/search",
             {"objective": q, "search_queries": [q], "mode": "fast",
              "advanced_settings": {"max_results": n}},
             {"x-api-key": keys["PARALLEL_API_KEY"], "Content-Type": "application/json"})
    return [i["url"] for i in (d.get("results") or []) if i.get("url")]

PROVIDERS = {"brave": search_brave, "exa": search_exa,
             "tavily": search_tavily, "parallel": search_parallel}

QUERIES = [
    "vercel.json schema validation",
    "python 3.13 free-threading status",
    "postgres index bloat monitoring",
    "RFC 9110 conditional requests",
]

def main():
    keys = load_keys()
    print(f"Providers with keys: {[k for k in PROVIDERS if k.upper()+'_API_KEY' in keys]}\n")
    print(f"{'query':<38} {'brave':>6} {'exa':>5} {'tavily':>7} {'parallel':>9}   overlap")
    print("-" * 92)
    totals = {p: 0 for p in PROVIDERS}
    pair_overlap = {}
    for q in QUERIES:
        results = {}
        with ThreadPoolExecutor(max_workers=4) as ex:
            futs = {ex.submit(fn, q, keys): name for name, fn in PROVIDERS.items()}
            for f, name in futs.items():
                try:
                    results[name] = {canonicalize(u) for u in f.result()}
                except Exception as e:
                    results[name] = set()
                    print(f"  [{name} error] {type(e).__name__}: {str(e)[:70]}", file=sys.stderr)
        counts = {p: len(results.get(p, set())) for p in PROVIDERS}
        for p in PROVIDERS:
            totals[p] += counts[p]
        print(f"{q[:37]:<38} {counts['brave']:>6} {counts['exa']:>5} "
              f"{counts['tavily']:>7} {counts['parallel']:>9}", end="   ")
        # pairwise overlap
        parts = []
        names = [p for p in PROVIDERS if results.get(p)]
        for i, a in enumerate(names):
            for b in names[i+1:]:
                inter = len(results[a] & results[b])
                union = len(results[a] | results[b])
                jac = inter / union if union else 0.0
                pair_overlap.setdefault((a, b), []).append((inter, union, jac))
                parts.append(f"{a[:3]}/{b[:3]}={inter}")
        print(" ".join(parts))
    print()
    print("=== pairwise Jaccard (0 = disjoint indexes, 1 = same index) ===")
    for (a, b), vals in sorted(pair_overlap.items()):
        inter = sum(v[0] for v in vals)
        union = sum(v[1] for v in vals)
        jac = inter/union if union else 0
        verdict = ("SAME UPSTREAM (suspicious)" if jac > 0.5 else
                   "independent" if jac < 0.35 else "partially shared")
        print(f"  {a:<9} × {b:<9} inter={inter:>3} union={union:>3} "
              f"J={jac:.3f}   {verdict}")
    print()
    print("totals:", {p: totals[p] for p in PROVIDERS})

if __name__ == "__main__":
    main()
