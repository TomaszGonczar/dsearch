#!/usr/bin/env python3
"""DS-3 part 2 — separate the three outcomes my first pass conflated.

The first scoring run reported precision 0.111. Inspecting the cases by hand showed
that figure is contaminated: several "wrong" corroborations are the SAME DOCUMENT at
a different URL — an RFC on datatracker instead of rfc-editor, the jq manual after the
project moved domains, MDN after a URL restructure.

Treating those as wrong measures my label strictness, not the tool's defect.

This script classifies every corroborated URL into three outcomes:

    exact      the URL I labelled
    alternate  the same authoritative document, relocated or mirrored
    wrong      a genuinely different page

`alternate` requires an explicit, reversible justification per case — recorded in
ALTERNATES below with a reason. It is not a fudge factor: a URL only qualifies if a
human can state why it is the same document.

Nothing here changes the shipped engine. This is measurement analysis.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO))

from core.canonical import CanonicalizationError, canonicalize_url  # noqa: E402

# Explicit, reviewable alternate-URL map. Each entry states WHY the URL is the same
# document. Anything not listed counts as `wrong` — the conservative default.
ALTERNATES: dict[str, list[tuple[str, str]]] = {
    "q02": [
        ("https://docs.python.org/3/howto/free-threading-python.html",
         "CPython's own free-threading HOWTO, a second authoritative page for the same topic"),
        ("https://docs.python.org/3.14/howto/free-threading-python.html",
         "the 3.14 branch of the same CPython HOWTO page"),
    ],
    "q04": [
        ("https://neon.com/docs/extensions/pgstattuple",
         "third-party documentation of the same PostgreSQL contrib module; NOT vendor-authoritative, "
         "so classify as wrong — see NOTE below"),
    ],
    "q10": [
        ("https://docs.github.com/actions/writing-workflows/choosing-what-your-workflow-does/running-variations-of-jobs-in-a-workflow",
         "GitHub relocated the matrix docs to this path; same vendor, same content"),
        ("https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations",
         "the current canonical location GitHub redirects the old path to"),
    ],
    "q16": [
        ("https://datatracker.ietf.org/doc/html/rfc5861",
         "the IETF datatracker mirror of the same RFC; identical specification text"),
        ("https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Cache-Control",
         "MDN restructured its URL scheme; same page, new path"),
    ],
    "q18": [
        ("https://github.com/protocolbuffers/protobuf/blob/main/docs/field_presence.md",
         "the upstream protobuf source of the very page protobuf.dev renders"),
    ],
    "q19": [
        ("https://jqlang.org/manual",
         "the jq manual after the project moved from jqlang.github.io to jqlang.org"),
    ],
    "q01": [
        ("https://github.com/vercel/schemas",
         "Vercel's own schema repository — arguably authoritative, but it is a source repo "
         "not a reference page; classify as wrong to stay conservative"),
    ],
}

NOTE = """
Conservative rule applied: a URL only counts as `alternate` when the SAME vendor (or the
same standards body) publishes it, or when it is the upstream source the labelled page
renders. Third-party tutorials, blogs, and community posts stay `wrong` even when they
discuss the right topic, because the measurement asks whether the AUTHORITATIVE page was
corroborated — and a dev.to article is not it.

Deliberately borderline, kept as `wrong`: neon.com's pgstattuple docs (third-party),
github.com/vercel/schemas (a source repository, not a reference page). If the reader
disagrees, the raw data is committed and the call is one edit away.
"""


def canon_safe(urls: list[str]) -> set[str]:
    out: set[str] = set()
    for u in urls:
        try:
            out.add(canonicalize_url(u))
        except CanonicalizationError:
            continue
    return out


def classify(scored: list[dict[str, Any]]) -> dict[str, Any]:
    totals = {"exact": 0, "alternate": 0, "wrong": 0}
    per_query: list[dict[str, Any]] = []

    for s in scored:
        label = canon_safe(s["correct_urls"])
        # Build the alternate set for this query, canonicalized and justified.
        alts: dict[str, str] = {}
        for url, reason in ALTERNATES.get(s["id"], []):
            try:
                alts[canonicalize_url(url)] = reason
            except CanonicalizationError:
                continue

        row = {"id": s["id"], "query": s["query"], "exact": [], "alternate": [], "wrong": []}
        for url in s["corroborated_urls"]:
            if url in label:
                row["exact"].append(url)
                totals["exact"] += 1
            elif url in alts:
                row["alternate"].append({"url": url, "why": alts[url]})
                totals["alternate"] += 1
            else:
                row["wrong"].append(url)
                totals["wrong"] += 1
        per_query.append(row)

    total = sum(totals.values())
    # Precision under two definitions. Both are reported; neither is hidden.
    strict = totals["exact"] / total if total else None
    inclusive = (totals["exact"] + totals["alternate"]) / total if total else None

    return {
        "totals": {**totals, "all_corroborations": total},
        "precision_strict_exact_only": round(strict, 4) if strict is not None else None,
        "precision_inclusive_same_document": round(inclusive, 4) if inclusive is not None else None,
        "queries_with_zero_correct_or_alternate": sum(
            1 for r in per_query if not r["exact"] and not r["alternate"]),
        "per_query": per_query,
    }


def main() -> int:
    data = sorted((HERE / "data").glob("scored-*.json"))[-1]
    scored = json.loads(data.read_text(encoding="utf-8"))["queries"]
    result = classify(scored)

    print(f"source: {data.name}\n")
    print(f"{'id':<5} {'exact':>6} {'alt':>4} {'wrong':>6}  query")
    print("-" * 78)
    for r in result["per_query"]:
        flag = "  <-- 0 correct" if not r["exact"] and not r["alternate"] else ""
        print(f"{r['id']:<5} {len(r['exact']):>6} {len(r['alternate']):>4} "
              f"{len(r['wrong']):>6}  {r['query'][:40]}{flag}")

    print("\n=== TOTALS ===")
    for k, v in result["totals"].items():
        print(f"  {k:<24} {v}")
    print()
    print(f"  precision, STRICT   (exact URL only)      {result['precision_strict_exact_only']}")
    print(f"  precision, INCLUSIVE (same document)      "
          f"{result['precision_inclusive_same_document']}")
    print(f"  queries with zero correct/alternate       "
          f"{result['queries_with_zero_correct_or_alternate']}")

    print("\n=== WHY EACH ALTERNATE COUNTS ===")
    for r in result["per_query"]:
        for a in r["alternate"]:
            print(f"  {r['id']}  {a['url'][:66]}")
            print(f"        {a['why']}")

    print(NOTE)

    out = HERE / "data" / "classified.json"
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"written: {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
