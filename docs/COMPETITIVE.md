# Competitive analysis — AllSearch MCP

> [!WARNING]
> Historical design comparison. It describes the proposed router before consensus precision was
> measured. dSearch was not completed as a product; use the [README](../README.md) for the result
> and current status.

**Reviewed:** [`Windrunner20/allsearch`](https://github.com/Windrunner20/allsearch) @ v0.2.0
(2 commits, 0 stars, Python 3.11+, ~590-line README)
**Verdict:** a real, working, well-engineered project solving a **different problem** from ours —
and it wins several comparisons outright. It also has one architectural choice that our entire
thesis argues against, and one technical claim that does not survive checking.

Written as a roast in both directions, because a comparison that only flatters us is useless.

---

## 1. The categorical difference

| | AllSearch | search-router |
|---|---|---|
| **Primary artifact** | `answer` — a generated answer from Grok | An attributed result set |
| **Model in the path** | **Yes, by design.** Grok-first; model answers, others supplement | **Never.** No model in the trust path |
| **Reproducible** | No — resampling gives a different `answer` | Yes — same bytes in, same hash out |
| **Verifiable later** | No | Yes — hash + provenance per result |
| **Consensus** | `跨 Provider 命中` (cross-provider hits) as *evidence metadata* | `consensus` as the **governing trust signal** |
| **Categorically** | Search **quality maximizer** | Search **integrity auditor** |

The one-line version:

> **AllSearch returns an answer. search-router returns a verdict with a receipt.**

### The roast that matters

AllSearch is Grok-first: a model produces the answer, then Tavily and AnySearch *supplement
evidence* around it. The `answer` field is the headline of every response.

That is the same move dcompact argues against for compaction — **wrap a probabilistic process
in a model summary and call it the output.** Compare:

| | Does this | Our position |
|---|---|---|
| OMP compaction | Model summarizes the conversation → prose | dcompact: prose is lossy, unverifiable, unportable |
| **AllSearch** | **Model summarizes search results → `answer`** | **search-router: same objection** |

An agent-fed `answer` is a claim with citations attached. If the model fabricates a citation,
AllSearch returns it *inside a citation list* — which makes it look more verified, not less.
There is no mechanism in the design for the tool to say *"I don't know whether this is right."*

Cost: one model call per search, every search. Latency: a model round-trip in the critical
path. Determinism: none.

---

## 2. Their independent-verification claim does not hold

This is the sharpest technical finding.

Their README states plainly:

> Tavily 适合补充网页结果和**做独立交叉验证**
> *(Tavily is suitable for supplementing web results and doing independent cross-validation)*

And the evidence block includes `跨 Provider 命中` — cross-provider hits.

**Tavily is not an independent index.** Per Brave's own comparison, Tavily "performs discovery
using its own crawler in tandem with third-party data aggregation." It is our class **B**:
independence is not a fixed property, so it cannot be relied on as a corroborating index.

So their "independent cross-validation" is computed across:

```
Grok (a language model's citations — possibly hallucinated)
  ×
Tavily (an aggregator — own crawler + licensed third-party data)
```

Neither side is a clean independent crawler. `跨 Provider 命中` therefore means *"a model said
this **and** an aggregator found it."* That is materially weaker than *"two independent crawlers
found this,"* and the design has no way to tell the difference.

**Their pipeline cannot detect this**, because it never asks what an index *is*. It asks which
provider answered.

Our [`PROVIDERS.md`](PROVIDERS.md) exists precisely because this failure is invisible from
inside a router.

---

## 3. Where AllSearch is simply better — and the adoption matrix

No hedging — these are real, and several should be adopted.

| AllSearch Feature | Why It Beats What We Had | Disposition |
|---|---|---|
| **Context budget with usage-aware tightening** (8 KB/16 KB caps; auto-tighten to 4 KB/2 KB above 75%/90% context) | Genuinely smarter than a flat byte budget. Adapts to agent context load. | **Adopted** (implemented in `core/budget.py`) |
| **`fetch` with SSRF hardening** (rejects localhost, private IPs, non-HTTP; re-validates redirect URL) | We had nothing on retrieval. Critical security requirement. | **Adopt** for any fetch tier |
| **Hard total deadline across all stages** (`ALLSEARCH_TOTAL_BUDGET_SECONDS`) | Bounds the whole operation rather than just per-provider timeouts. | **Adopt** |
| **Circuit breaker per provider** with state | Failover without memory pointlessly retries dead providers. | **Adopt** |
| **Strict mode refuses rather than substituting** (`ALLSEARCH_ALLOW_DEGRADED_SEARCH=false`) | Matches our "never a silent empty" principle. | **Adopt** naming convention |
| **Depth-by-intent naming** (`fast` / `balanced` / `verify` / `deep`) | Describes *task intent* rather than setup burden (Tier 0–3 API keys). | **Adopt** |
| **Key pools with round-robin + quota failover** | Practical production resiliency. | Plan for multi-key ops |
| **`route.stages` per-call latency reporting** | Honest observability and attribution. | Retain in attribution |
| **Secret redaction before returning to agent** | Essential before untrusted transcript ingestion. | Plan for packaging |
| **Working code, offline test suite** | Concrete empirical tests beat concept documents. | **Adopted** (78 offline tests) |

**Their depth model is also a better UX than our tiers.** `fast` / `balanced` / `verify` /
`deep` describes *task intent*. Our Tier 0–3 describes *setup burden* — how many API keys you
bought. A user can reason about "I need verification"; nobody wants to reason about "I have
two keys, therefore Tier 2."

---

## 4. Where we are genuinely different, and it is not cosmetic

Four things, in order of how hard they'd be for AllSearch to copy.

### 4.1 The audit ledger — the thing neither of us has

Their `route.stages` is **per call**. Nothing accumulates. After a week of use, a user still
cannot answer the question this project exists to ask:

> *"How many searches were corrupted? 14 searches, 3 empty, 2 single-source."*

Their `health` tool reports provider state, not history. Our §6 open question 3 was whether the
counter is the headline feature. Reading their design settles it: **it is.** They built
excellent per-call diagnostics and no memory, which means the corruption rate remains
unmeasurable even with a better search stack.

### 4.2 Consensus as the governing signal, not evidence metadata

Theirs: merge, rank, dedupe, and *report* cross-provider hits.
Ours: compute agreement first, and let it **govern** the result — `consensus: true` on the
result itself, and single-source results explicitly marked as such.

The difference is who acts on it. Their agent reads an `answer` and may or may not notice an
evidence count. Our result set carries the trust level on each item.

### 4.3 Disagreement as a first-class output — **nobody does this**

A new mechanism, falling directly out of the consensus computation, and absent from AllSearch,
`reliable-web-search`, and every Multi-Search MCP I examined:

Their pipeline **merges away** divergence. If Brave and Exa return disjoint result sets, the
merge produces a union and the fact that they agreed on *nothing* is lost.

But for a research task, disagreement between independent indexes is **the single most
important thing you could tell the agent**:

- Query is ambiguous → the two indexes interpreted it differently
- Topic is contested → the indexes surface different camps
- One index has a coverage gap for this domain

```
[search-router] vercel.json schema validation

⚠ NO CONSENSUS — 0 of 8 results confirmed by both indexes
  brave: 5 results · exa: 5 results · overlap: 0
  → these independent indexes agree on nothing.
    treat as: ambiguous query or contested topic. verify before planning.
```

Neither a merge-and-rank pipeline nor a Grok-first answer can produce that line, because both
are structurally committed to producing *something coherent*. An auditor's job includes
reporting that the evidence does not cohere.

**This is the strongest unique mechanism available to us.**

### 4.4 No model in the trust path

`verify` depth in AllSearch re-runs Grok and gets a different answer. Ours returns the same
bytes and a hash. That is the difference between a tool you can audit and a tool you must
trust.

---

## 5. What we explicitly reject

- **Grok-first, or any model producing the headline artifact.** It forfeits determinism,
  reproducibility, and auditability in one move — the three things this project is for.
- **Cross-provider hits over a model × aggregator pair.** Compute consensus over independent
  indexes, or label it honestly as something weaker.
- **Treating supplementation as verification.** Adding a provider improves coverage. It does not
  establish truth, and the two must not share a name.

---

## 7. The positioning, stated once

```
AllSearch:       more providers → better answer
                 (quality maximizer, model in the loop)

search-router:   measured agreement → known trust level
                 (integrity auditor, no model in the path)
```

They are not competitors. They are adjacent products with a shared substrate — and a user
could reasonably run both: AllSearch for a fast answer, search-router to know whether the
answer's evidence holds.

**The honest summary:** AllSearch is ahead of us on execution by a wide margin and ahead on
context ergonomics outright. We are ahead on exactly one axis — *whether the result can be
trusted and counted* — and that axis has to be the whole product or there is no reason to
build it.

## 8. Evidence

- Competitor: `https://github.com/Windrunner20/allsearch` (README read in full, 590 lines)
- Tavily index provenance: Brave's comparison — *"Tavily performs discovery using its own
  crawler in tandem with third-party data aggregation"* ([brave.com/learn/best-search-api-2026](https://brave.com/learn/best-search-api-2026/))
- Their self-declared limits: in-process cache only, no Docker image, no LICENSE file despite
  MIT metadata, ranking/query-rewrite still being tuned
