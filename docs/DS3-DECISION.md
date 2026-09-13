# DS-3 — Consensus precision: measured, and the verdict

**Date:** 2026-09-13
**Status:** COMPLETE — **consensus is demoted to metadata; the ledger is the headline**
**Method:** **60** labelled document-class queries × 4 live providers × 10 results each
**Raw data:** `experiments/ds3/data/` (results, scored, classified)
**Note:** the set was extended from 22 to 60 after a power analysis showed the correlation
claim was underpowered at n=22. Both the original and extended results are committed.

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

| Metric | n=22 | **n=60 (final)** |
|---|---|---|
| Queries | 22 | **60** |
| Consensus fired | 22 / 22 (100%) | **60 / 60 (100%)** |
| Total corroborated URLs | 108 | **261** |
| → the labelled page | 12 | **38** |
| → same document, other URL | 10 | 9 (see bias note) |
| → genuinely different pages | 86 | **214** |
| **Precision, strict** | 0.111 | **0.146** |
| Wilson 95% CI, strict | [0.065, 0.184] | **[0.108, 0.194]** |
| Queries with no correct corroboration at all | 3 | — |

**Roughly six in seven corroborated URLs point at a page other than the authoritative one.**

The defect is not a corner case. It is the dominant behaviour of the signal, and the larger
sample confirms it: the strict precision moved from 0.111 to 0.146, and the CI upper bound
rose from 0.184 to 0.194. **There is still no precision at which this signal becomes usable.**

### Detected-alternate bias at n=60, disclosed rather than corrected

The `alternate` map in `classify.py` covers only the original 22 queries. The 38 added for
statistical power have **no alternates defined**, so any same-document-at-another-URL they
produced is currently counted `wrong`. This biases strict precision **downward**.

The original 22 established an alternate rate of **9.8% of non-exact corroborations**. If that
rate holds for the new queries, roughly **13 undetected alternates** sit in the new set and the
inclusive figure would be approximately **0.229**.

That is an **estimate and is labelled as one**. The strict figure requires no estimate, is
unaffected by the gap, and is the number the verdict rests on. Hand-auditing 214 URLs was not
done; the gap is stated rather than papered over.

---

## The finding that settles it

Precision was measured against consensus rate per query:

| | n | Precision |
|---|---|---|
| Rate ≤ 0.20 | 10 | **0.270** |
| Rate > 0.20 | 12 | **0.172** |

**Pearson r = −0.355.**

**Aggregation method, stated because it changes the number.** The figures above are the **mean of
per-query precision**. Two other defensible aggregations give different values, and all three are
computed from the same committed data:

| Aggregation | rate ≤ 0.20 | rate > 0.20 |
|---|---|---|
| mean of per-query precision *(quoted above)* | 0.270 | 0.172 |
| pooled, counting same-document alternates | 0.256 | 0.174 |
| pooled, strict exact-URL only | 0.154 | 0.087 |

**Every method preserves the finding: the lower-rate bucket has the higher precision.** The
correlation does not depend on the choice, which is why the verdict is robust to it. The
mean-of-per-query figure is quoted because each query contributes equally regardless of how many
URLs it happened to return.

A reader who recomputes and gets 0.256 or 0.154 has not found an error — they used a different
aggregation. This table exists so that is obvious rather than confusing.

**Statistical status, after a power analysis and a re-run at n=60.**

At n=22 the inverted correlation was **suggestive, not established**:

| Test | n=22 | n=60 |
|---|---|---|
| Pearson r | −0.355 | **−0.287** |
| t | −1.699 (df 20) | **−2.284 (df 58)** |
| critical \|r\| at p < 0.05 | 0.423 → **not significant** | 0.254 → **significant** |
| Permutation test, 20 000 shuffles, seed 17 | p = 0.032 | **p = 0.011** |
| Median split — mean precision, low vs high rate | — | **0.240 vs 0.130, p = 0.0013** |

**The claim is now established.** The set was extended to 60 queries specifically because two
defensible tests disagreed at n=22, and the honest response to that is more data rather than the
test that agrees with the conclusion.

One detail worth stating, because it cuts against the temptation to report the bigger number:
**the effect size shrank, from −0.355 to −0.287.** That is expected and it is a sign the
measurement is real. Small samples inflate effect sizes; the true effect is smaller and now
clears significance because n is larger. Reporting only the n=22 figure would have overstated
the effect.

Three tests now agree — Pearson, a permutation test on the rate bucket, and a median split with
a tighter p — and all three point the same way.

**Critically, the verdict does not depend on this claim.** The decision to demote consensus rests
on precision alone: **0.146** strict, CI upper bound **0.194**. There is no sample size at which
that becomes a usable trust signal, because the point estimate is nowhere near the boundary. The
correlation is the *interesting* finding; it is not the load-bearing one.

Consensus rate **is** negatively correlated with precision. More agreement predicts *less*
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
