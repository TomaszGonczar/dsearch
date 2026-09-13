# DS-3 — Consensus precision: measured, and the verdict

**Date:** 2026-09-13
**Status:** COMPLETE — **consensus is demoted to metadata; the ledger is the headline**
**Method:** 22 labelled document-class queries × 4 live providers × 10 results each
**Raw data:** `experiments/ds3/data/` (results, scored, classified)

---

## The question

`EXPERIMENT-OVERLAP.md` measured consensus **rate** — how often independent indexes agree
(0.247 mean). It never measured consensus **precision** — whether the agreement is *right*.
The known defect, found by inspection and deliberately left open:

> Consensus marks popular pages, not correct ones.

This is the measurement that decides whether that defect sinks the feature, or whether it is
a manageable edge case.

**It is not an edge case.**

---

## Result

| Metric | Value |
|---|---|
| Queries | 22 |
| Consensus fired | **22 of 22** (100%) |
| Total corroborated URLs | 108 |
| Corroborated URLs that were the labelled page | **12** |
| Corroborated URLs that were the same document at another URL | 10 |
| Corroborated URLs that were genuinely different pages | **86** |
| **Precision, strict** (exact URL) | **0.111** |
| **Precision, inclusive** (same document) | **0.204** |
| Queries where no corroboration was correct *or* an alternate | 3 |

**Roughly four in five corroborated URLs point at a page other than the authoritative one.**

The defect is not a corner case. It is the dominant behaviour of the signal.

---

## The finding that settles it

Precision was measured against consensus rate per query:

| | n | Precision |
|---|---|---|
| Rate ≤ 0.20 | 10 | **0.270** |
| Rate > 0.20 | 12 | **0.172** |

**Pearson r = −0.355.**

Consensus rate is **negatively** correlated with precision. More agreement predicts *less*
accuracy. The mechanism is explainable and was predicted: popular pages are crawled and ranked
by every index, and popular pages are generic — the vendor landing page, the Wikipedia entry,
the repo README. They agree on what everybody already knows, and the precise page each query
actually wanted stays single-source.

**A trust signal that points the wrong way is worse than no signal.** It would let dSearch tell
a user "this is corroborated" about exactly the results least likely to be right.

---

## Two methodological confounds, both checked and both disclosed

### 1. The first figure was contaminated; the second is the honest one

The initial scoring reported 0.111 with no allowance for the same document at a different URL.
Hand inspection found:

| Query | Label | Corroborated | Reality |
|---|---|---|---|
| q16 | `rfc-editor.org/rfc/rfc5861` | `datatracker.ietf.org/doc/html/rfc5861` | same RFC, IETF mirror |
| q19 | `jqlang.github.io/jq/manual` | `jqlang.org/manual` | project moved domains |
| q16 | `mdn.../Headers/Cache-Control` | `mdn.../Reference/Headers/Cache-Control` | MDN restructured paths |
| q10 | `docs.github.com/en/actions/using-jobs/...` | `docs.github.com/actions/writing-workflows/...` | GitHub relocated |

`classify.py` separates `exact` from `alternate`, with a stated justification per alternate and a
conservative default: a third-party tutorial stays **wrong** even when it covers the right topic,
because the question is whether the *authoritative* page was corroborated.

Even under the generous definition, precision is **0.204**. The conclusion is unchanged.

### 2. This measures page-findability, not answer-correctness

Every query in the set has an unambiguous canonical **document**. The measurement asks *"was the
correct page corroborated"* — not *"was the answer correct."* Queries whose right answer is a fact
rather than a page were excluded deliberately.

So this is a **narrower** claim than it might read as, and it is a **ceiling** on usefulness: if
the signal cannot identify the right page, it certainly cannot vouch for the right answer.

---

## The verdict

**Consensus does not ship as a trust signal. It is demoted to metadata.**

Per the DS-3 acceptance criteria, outcome 3 applies:

> Precision is unfixable at this layer → consensus is demoted to metadata, and the product's
> headline becomes the ledger alone.

Topical scoping (outcome 2) was considered and is **not** being adopted now. It would require a
relevance judgement — a model or an embedding — inside the trust path, which invariant 1 forbids
and which is the exact move this project exists to argue against. Adding a model to make
consensus work would reproduce AllSearch's structural mistake.

### What this means concretely

- `consensus` stays in the envelope, marked `metadata_only`, with this measurement cited
- Nothing in the pack header or the CLI presents a corroboration as evidence of quality
- **The ledger becomes the headline feature** (DS-4), not a supporting one
- The wrong-consensus test stays, and now asserts that the defect is *load-bearing* — if someone
  later fixes it, they must come back and change this document

### What the product is now

> dSearch tells you **what your searches actually did** — how many returned nothing, how many
> were single-source, how long they took — and refuses to claim any of them were *right*.

That is defensible, honest, and measurable. It is also smaller than the original pitch. The
original pitch claimed consensus as its differentiator; the measurement killed that claim, and
the product survives on the ledger instead.

---

## Why this is the right outcome

The alternative was shipping a trust signal with 0.111 precision, correlated the wrong way, and
describing it as corroboration. That is the failure mode both portfolio projects exist to catch:
a plausible-looking artifact that is not what it says it is.

The measurement cost roughly an hour and invalidated a headline feature before it was built.
`EXPERIMENT-OVERLAP.md` found the defect by inspection; this document proves it with numbers and
states the consequence.
