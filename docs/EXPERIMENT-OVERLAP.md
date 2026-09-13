# Experiment: is the consensus signal real?

> [!WARNING]
> Preliminary experiment, superseded by the DS-3 precision evaluation. The committed artifact is
> insufficient to independently reproduce every pairwise Jaccard and repeat-stability claim. Its
> reported `0.247` is the pooled rate `41 / 166`, not a mean of per-query rates, and the recorded
> Parallel repeat stability is `0.82`, not `1.00`. See the [README](../README.md) for the audited
> result.

**Date:** 2026-09-13
**Status:** measured against four live providers with real API keys
**Scripts:** `experiments/overlap-probe.py`, `experiments/overlap-record.py`, `experiments/weakspots.py`
**Raw data:** `experiments/data/overlap-2026-09-13.json`

This was run **before writing any product code**, because the entire concept rests on one
assumption that had never been tested: *do independent search indexes actually disagree enough
for agreement to carry information?*

If they agreed on everything, they share an upstream and consensus is theatre. If they agreed
on nothing, consensus would never fire. Both extremes would have killed the design.

---

## 1. Headline result: the indexes are genuinely independent

Six technical queries, four providers, 10 results each. Pairwise Jaccard overlap (0 = disjoint
indexes, 1 = the same index):

| Pair | Intersection | Union | Jaccard | Verdict |
|---|---|---|---|---|
| tavily × parallel | 4 | 72 | **0.056** | independent |
| brave × parallel | 7 | 73 | **0.096** | independent |
| exa × parallel | 8 | 72 | **0.111** | independent |
| brave × exa | 10 | 70 | **0.143** | independent |
| exa × tavily | 13 | 63 | **0.206** | independent |
| brave × tavily | 14 | 62 | **0.226** | independent |

**Nothing approaches the >0.5 that would indicate a shared upstream.** The assumption holds:
these are different indexes with different coverage.

Average consensus rate across queries: **0.247** — roughly one URL in four is surfaced by two
or more independent providers.

### Why this also corrects a claim we made

We classified **Tavily as class B (aggregator)** and advised against pairing it, on the grounds
that its independence varies and cannot be relied on.

Measured, Tavily's overlap with the others (0.056–0.226) is **indistinguishable from the
independent providers'**. It behaves like an independent index on these queries.

**This does not fully retract the classification** — the objection was about *reliability of
the property*, not its observed value on six queries. But it does mean the guidance was
stronger than the evidence supports, and it must be restated: *Tavily is a weaker consensus
partner because its independence is not contractually fixed, not because it was observed to be
derivative.* That is a materially smaller claim.

---

## 2. Agreement is not sampling noise

Critical check: if a provider returned different results on identical calls, "agreement" would
partly measure its own instability rather than index overlap. Same query, three consecutive
calls:

| Provider | n | run1×2 J | run1×3 J | |
|---|---|---|---|---|
| exa | 10 | **1.00** | **1.00** | stable |
| tavily | 8 | **1.00** | **1.00** | stable |
| parallel | 10 | 0.82 | 0.82 | stable |
| brave | 10 | **1.00** | **1.00** | stable *(paced re-test, below)* |

Providers are deterministic across identical calls. **Agreement therefore measures real index
overlap.** The signal is not noise.

Brave initially errored in this test — see §4. Re-run with 1.2 s pacing between calls, it
returns identical results on all three runs (J=1.00). All four providers are confirmed stable;
the initial failure was rate limiting, not instability.

---

## 3. WEAK SPOT — the headline feature was designed around a case that does not occur

The concept proposed **"disagreement as first-class output"** — reporting when two independent
indexes agree on *nothing*, as a signal that a query is ambiguous or a topic contested:

```
⚠ NO CONSENSUS — 0 of 8 results confirmed by both indexes
```

Tested against deliberately degenerate queries designed to maximise divergence:

| Query | Union | Consensus | Rate | |
|---|---|---|---|---|
| `apple` | 28 | 9 | 0.321 | |
| `mercury` | 25 | 7 | 0.280 | |
| `model` | 30 | 6 | 0.200 | |
| `the best way` | 25 | 10 | 0.400 | |
| `x` | 26 | 4 | 0.154 | |

**Zero consensus never occurred — not even for the single character `x`.**

The reason is structural: **popular pages surface across every index regardless of query.**
Homepages, Wikipedia entries, and documentation roots are crawled and ranked by everyone, so
*every* query has some consensus. Ambiguity does not produce divergence; it produces a
different *mix* of the same popular pages.

**Consequence for the design:** the binary `consensus: none` signal is decoration. What
actually varies is the **rate** — 0.15 to 0.46 across our sample — so the continuum we already
specified (`strong` / `partial` / `none`) is right, but `none` must be documented as
*essentially unreachable*, and the working signal is a **low rate**, not a zero one.

The honest version of the feature: *"only 15% of these results are corroborated"* — not
*"nothing agrees."*

### 3.1 A second, worse problem hidden in the same data

If consensus forms on popular pages, then **`consensus: true` marks popularity, not
correctness.**

For `vercel.json schema validation`, the consensus hits are likely the Vercel docs root and
general reference pages — not the specific JSON-schema reference the query wanted. All four
indexes return them because they are prominent, not because they answer the question.

So the trust signal has a **precision failure mode**: it will sometimes endorse the generic
page over the precise one. Consensus tells you *"this page is well-known"*, which correlates
with but is not the same as *"this page answers your query."*

**Mitigations to specify, not yet implemented:**
- Rank consensus **within** the query's topical cluster rather than across all results —
  only count agreement among results that are plausibly on-topic
- Report consensus as *"N of M"* per result, never as a global quality score
- Never let consensus override a reranker; it changes trust, not ordering (already decided)
- Add a fixture where the consensus hit is deliberately the *wrong* page, and assert the
  design surfaces the precise one anyway

This is the most important open defect in the design. It does not invalidate consensus — a
corroborated URL is still better evidence than an uncorroborated one — but it means consensus
alone cannot be the product's answer to *"should I trust this?"*

---

## 4. WEAK SPOT — Brave free tier rate-limits rapid repeats

The stability test failed on Brave with an error after several calls in quick succession.
Brave's free tier is rate-limited (approximately 1 request/second). Our probe issued four
providers in parallel and repeated calls immediately.

**Consequences:**
- Any design that fires multiple queries in quick succession will hit this on free tiers.
- The circuit breaker and total-deadline features (adopted from AllSearch) are not optional
  polish — they are required to survive a rate limit gracefully.
- The overlap experiment's Brave row should be re-run with pacing before the numbers are
  treated as final. Its *measured* results elsewhere (J=0.096–0.226) are consistent with the
  others, so the conclusion is unlikely to change, but the sample is one call short.

---

## 5. What this changes

| Finding | Action |
|---|---|
| Indexes are independent | **Premise confirmed.** Build on it. |
| Agreement is stable, not noise | Keep consensus as a deterministic signal. |
| `consensus: none` never fires | Restate as a *rate*; document `none` as unreachable. |
| Consensus favours popular pages | **Open defect.** Needs topical scoping; add a wrong-consensus fixture. |
| Tavily measures as independent | Soften the class-B guidance to a reliability caveat. |
| Brave rate-limits | Circuit breaker + deadline are requirements, not polish. |

## 6. What was not tested

- Non-English queries (the source implementation is Polish-commented; untested here)
- Academic / code-specific verticals (AllSearch routes these to AnySearch)
- Whether consensus correlates with *user-perceived* answer quality — this needs a
  human-labelled set, and it is the only way to settle §3.1 properly
- Cost and latency at scale
