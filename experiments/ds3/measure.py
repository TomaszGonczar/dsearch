#!/usr/bin/env python3
"""DS-3 — measure consensus PRECISION against the labelled evaluation set.

The question this answers:

    When consensus fires, how often is the corroborated URL actually the CORRECT one?

The shipped `docs/EXPERIMENT-OVERLAP.md` measured the consensus *rate* (how often
agreement happens: 0.247 mean). It never measured *precision* (whether the agreement
is right). The known defect — consensus marks popular pages, not correct ones — was
found by inspection and left open. This is the measurement that decides whether that
defect sinks the feature.

DESIGN CONSTRAINTS

1. **No circularity.** Labels live in `eval-set.json`, authored before any provider was
   queried. This script never writes labels. It reads them and scores against them.

2. **Reuses the shipped engine.** Scoring calls `core.consensus.compute_consensus`
   directly — the same function the product ships. Reimplementing the metric here would
   measure a different thing than the product does.

3. **Records raw provider output.** Every URL returned is written to the result file, so
   the measurement can be re-scored later without re-querying (and so a reader can check
   the scoring by hand rather than trusting it).

4. **Live network, opt-in, off CI.** Invariant 10 forbids network in tests. This is an
   experiment script, not a test, and it prints that boundary.

Usage:
    python3 experiments/ds3/measure.py              # full run, uses API keys
    python3 experiments/ds3/measure.py --score-only # re-score recorded results
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DATA = HERE / "data"

sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "experiments"))

# Reuse the shipped engine. Do not reimplement the metric.
from core.canonical import CanonicalizationError, canonicalize_url  # noqa: E402
from core.consensus import compute_consensus  # noqa: E402
from providers.registry import load_registry  # noqa: E402

# Reuse the probe's provider adapters rather than duplicating transport code.
_probe_src = (REPO / "experiments" / "overlap-probe.py").read_text(encoding="utf-8")
exec(_probe_src.split("def main()")[0])  # noqa: S102


def load_eval_set() -> dict[str, Any]:
    return json.loads((HERE / "eval-set.json").read_text(encoding="utf-8"))


def query_all_providers(query: str, keys: dict[str, str], n: int = 10) -> dict[str, list[str]]:
    """Query every provider with a key. Returns raw URL lists — never filtered."""
    from concurrent.futures import ThreadPoolExecutor

    out: dict[str, list[str]] = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(fn, query, keys, n): name for name, fn in PROVIDERS.items()}
        for fut, name in futs.items():
            try:
                out[name] = [str(u) for u in fut.result()]
            except Exception as exc:  # noqa: BLE001 — a dead provider is data, not a crash
                out[name] = []
                print(f"    [{name}] {type(exc).__name__}: {str(exc)[:70]}", file=sys.stderr)
    return out


def _is_unparseable(url: str) -> bool:
    try:
        canonicalize_url(url)
    except CanonicalizationError:
        return True
    return False


def canonicalize_safe(urls: list[str]) -> set[str]:
    """Canonicalize, skipping unparseable URLs.

    Provider output is untrusted input. A truncated port or non-HTTP scheme must not
    abort scoring — the same defect class found in `core/consensus.py` while running
    this measurement. Skipped URLs are counted, never silently dropped.
    """
    out: set[str] = set()
    for url in urls:
        try:
            out.add(canonicalize_url(url))
        except CanonicalizationError:
            continue
    return out


def score_query(entry: dict[str, Any], provider_urls: dict[str, list[str]],
                registry: dict[str, Any]) -> dict[str, Any]:
    """Score one query. Pure function; no I/O."""
    report = compute_consensus(provider_urls, registry)
    correct = canonicalize_safe(entry["correct_urls"])

    # Which correct URLs did each provider return, ignoring consensus entirely?
    per_provider_hits = {
        name: sorted(canonicalize_safe(urls) & correct)
        for name, urls in provider_urls.items()
    }
    any_provider_found = any(per_provider_hits.values())
    unparseable_total = sum(
        sum(1 for u in urls if _is_unparseable(u)) for urls in provider_urls.values())

    corroborated = set(report.corroborated_urls)
    correct_corroborated = corroborated & correct
    wrong_corroborated = corroborated - correct

    # The metric that matters. Only defined when consensus actually fired.
    consensus_fired = len(corroborated) > 0
    precision: float | None
    if consensus_fired:
        precision = len(correct_corroborated) / len(corroborated)
    else:
        precision = None

    return {
        "id": entry["id"],
        "query": entry["query"],
        "authoritative_because": entry["authoritative_because"],
        "correct_urls": sorted(correct),
        "provider_url_counts": {k: len(v) for k, v in sorted(provider_urls.items())},
        "unparseable_urls": unparseable_total,
        "correct_found_by_any_provider": any_provider_found,
        "per_provider_correct_hits": per_provider_hits,
        "consensus_status": str(report.status),
        "consensus_rate": report.rate,
        "corroborated_urls": sorted(corroborated),
        "correct_corroborated": sorted(correct_corroborated),
        "wrong_corroborated": sorted(wrong_corroborated),
        "consensus_fired": consensus_fired,
        "precision": precision,
        "defect_observed": bool(wrong_corroborated) and not correct_corroborated,
    }


def aggregate(scored: list[dict[str, Any]]) -> dict[str, Any]:
    fired = [s for s in scored if s["consensus_fired"]]
    total_corroborated = sum(len(s["corroborated_urls"]) for s in fired)
    total_correct = sum(len(s["correct_corroborated"]) for s in fired)
    return {
        "queries": len(scored),
        "consensus_fired": len(fired),
        "consensus_did_not_fire": len(scored) - len(fired),
        "total_corroborated_urls": total_corroborated,
        "total_correct_corroborated": total_correct,
        # Pooled precision: correct corroborations / all corroborations.
        "pooled_precision": (round(total_correct / total_corroborated, 4)
                             if total_corroborated else None),
        "mean_per_query_precision": (
            round(sum(s["precision"] for s in fired) / len(fired), 4) if fired else None),
        "queries_where_defect_observed": sum(1 for s in scored if s["defect_observed"]),
        "queries_where_correct_found_but_not_corroborated": sum(
            1 for s in scored if s["correct_found_by_any_provider"]
            and not s["correct_corroborated"]),
        "queries_correct_never_found": sum(
            1 for s in scored if not s["correct_found_by_any_provider"]),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--score-only", action="store_true",
                    help="re-score the recorded results without querying providers")
    ap.add_argument("--results", default=None, help="results file to score")
    args = ap.parse_args()

    DATA.mkdir(parents=True, exist_ok=True)
    eval_set = load_eval_set()
    registry = load_registry()

    if args.score_only:
        path = Path(args.results) if args.results else sorted(DATA.glob("results-*.json"))[-1]
        record = json.loads(path.read_text(encoding="utf-8"))
        print(f"re-scoring {path.name} ({len(record['queries'])} queries)\n")
    else:
        print("LIVE NETWORK — this is an experiment script, not a test.")
        print("Invariant 10 forbids network in the test suite; this is excluded deliberately.\n")
        keys = load_keys()
        configured = [p for p in PROVIDERS if f"{p.upper()}_API_KEY" in keys]
        print(f"providers with keys: {configured}\n")
        measured: list[dict[str, Any]] = []
        for entry in eval_set["queries"]:
            print(f"  {entry['id']}  {entry['query'][:52]}")
            urls = query_all_providers(entry["query"], keys)
            measured.append({"id": entry["id"], "provider_urls": urls})
        record = {
            "measured_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "eval_set_authored_at": eval_set["_meta"]["authored_at"],
            "providers_configured": configured,
            "queries": measured,
        }
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = DATA / f"results-{stamp}.json"
        out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"\nraw results written: {out.relative_to(REPO)}")

    by_id = {q["id"]: q for q in eval_set["queries"]}
    scored = [score_query(by_id[r["id"]], r["provider_urls"], registry)
              for r in record["queries"]]

    print(f"\n{'id':<5} {'status':<12} {'rate':>6} {'corrob':>7} {'right':>6} "
          f"{'wrong':>6} {'prec':>6}  query")
    print("-" * 104)
    for s in scored:
        rate = f"{s['consensus_rate']:.2f}" if s["consensus_rate"] is not None else "  - "
        prec = f"{s['precision']:.2f}" if s["precision"] is not None else "  - "
        flag = "  <-- DEFECT" if s["defect_observed"] else ""
        print(f"{s['id']:<5} {s['consensus_status']:<12} {rate:>6} "
              f"{len(s['corroborated_urls']):>7} {len(s['correct_corroborated']):>6} "
              f"{len(s['wrong_corroborated']):>6} {prec:>6}  {s['query'][:38]}{flag}")

    agg = aggregate(scored)
    print("\n=== AGGREGATE ===")
    for k, v in agg.items():
        print(f"  {k:<48} {v}")

    stamp = record["measured_at"].replace(":", "").replace("-", "")[:15]
    scored_path = DATA / f"scored-{stamp}.json"
    scored_path.write_text(
        json.dumps({"aggregate": agg, "queries": scored}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(f"\nscored written: {scored_path.relative_to(REPO)}")

    print("\n=== READING THIS RESULT HONESTLY ===")
    print("This measures whether the correct PAGE was corroborated, not whether the")
    print("answer was correct. Queries whose right answer is a fact rather than a")
    print("document are out of scope and were excluded from the set.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
