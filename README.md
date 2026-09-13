# dSearch: when search consensus pointed the wrong way

**This is a completed falsification record, not a working search product.**

Four search providers were queried, and the eligible independent indexes agreed often enough
to look useful. On 60 labelled document queries, that agreement identified the labelled page
in only **38 of 261 corroborated URLs: 14.6% strict precision** (Wilson 95% CI
**[10.8%, 19.4%]**). Development stopped before the signal could be presented as trust.

**The mechanism worked. The hypothesis did not.**

[Result](#the-result) · [Method](#how-it-was-tested) · [Decision](#the-engineering-decision) ·
[Audit notes](#what-the-evidence-does-not-establish) · [Reproduce](#reproduce-the-verifiable-core)

> [!IMPORTANT]
> dSearch is a research artifact. It preserves the hypothesis, deterministic core, measurement
> harness, raw provider results, and the mistakes found during verification. It is not an
> end-to-end router, supported package, or recommendation to use consensus as a quality signal.

## The result

The proposed trust signal was simple: if independent search indexes return the same canonical
URL, that page has corroboration unavailable from a single provider.

The signal was measurable and frequent. It was not informative enough to ship.

| Prediction | Measurement | Outcome |
|---|---:|---|
| Provider agreement identifies the right page | **38 / 261 = 0.1456** strict precision | Falsified |
| `consensus: none` exposes ambiguity | Consensus fired in **60 / 60** evaluation queries | Falsified in this sample |
| More agreement means greater confidence | Exploratory inclusive analysis: **r = -0.287**, two-sided **p = 0.026** | Inverted in this sample |

The third result is the surprising one: agreement did not merely add little information. In the
recorded evaluation it moved in the wrong direction. A plausible mechanism is popularity:
generic documentation roots, repository pages, and other widely indexed URLs are easy for
providers to agree on, even when a query asks for one precise authoritative page.

The correlation is reported as **exploratory**, not established. Its classification and
provenance limitations are stated below. The load-bearing result is strict precision:
`38 / 261`, which does not depend on alternate-URL judgements.

## Why test this before building the router

The project started from a real agent failure. Three web searches returned zero results without
surfacing a useful failure to the model; one call consumed **264 seconds**. The agent continued
planning on an empty evidence base.

dSearch separated two questions:

1. Did search return an attributed, bounded outcome rather than a silent empty?
2. Can cross-provider URL agreement say whether the result deserves trust?

The first question produced useful deterministic components. The second was the proposed
differentiator, so it was measured before provider orchestration, packaging, or integrations
were built around it. The measurement killed that feature.

## How it was tested

- **60 document-finding queries** with one or more labelled authoritative URLs.
- **Four providers**, requesting up to 10 results from each.
- URLs canonicalized before comparison: scheme, `www`, trailing slash, and tracking parameters.
- A URL counted as consensus when at least two eligible providers returned it.
- Strict precision counted only canonical matches to a labelled URL.
- Raw responses, per-query scores, and classifications were committed under
  [`experiments/ds3/data/`](experiments/ds3/data/).

The evaluation was first run at 22 queries, where strict precision was `12 / 108 = 0.1111`
(Wilson 95% CI `[0.065, 0.184]`), then extended to 60. The final strict result was
`38 / 261 = 0.1456` (Wilson 95% CI `[0.108, 0.194]`).

This measures **page findability**, not answer correctness. It asks whether agreement recovers a
labelled document. It does not test whether an answer synthesized from the results is correct.

## The engineering decision

Consensus was demoted from a trust signal to descriptive metadata, and product work stopped.
Topical scoping was not used to rescue it: deciding whether a page is relevant would require a
model or another semantic judge inside the trust path, replacing a failed transparent signal
with a harder-to-audit one.

What remains technically valid:

- deterministic attributed envelopes, including explicit zero-result outcomes;
- URL canonicalization and pairwise agreement rates;
- context-aware output budgets;
- offline provider contract fixtures;
- explicit provider independence classes stored as configuration;
- graceful handling of malformed provider URLs;
- **78 offline tests** covering the pure core and provider contracts.

These components are evidence of the experiment, not a claim that dSearch is a complete tool.

## What the evidence does not establish

An adversarial verification pass reproduced the strict result and found limitations that matter:

- Two URLs are counted as `alternate` by
  [`classify.py`](experiments/ds3/classify.py) even though their own annotations say they must
  remain `wrong`. The committed measured-inclusive value is therefore `0.1801`; applying the
  script's stated conservative rule gives `45 / 261 = 0.1724`. **Strict precision is unchanged.**
- Repository history does not prove that labels predated provider calls. The result files have
  measurement timestamps earlier than the commits that first contain their labels, while the
  label metadata timestamps are later still. This is a provenance failure, not proof that the
  labels were derived from provider output.
- The committed overlap summary does not contain the raw URLs or repeated-call runs needed to
  independently reproduce its pairwise Jaccard and stability claims. Its document records
  Parallel repeat stability at `J = 0.82`, not `1.00`.
- The permutation, median-split, and domain-precision calculations were not committed as code.
  Their p-values depend on an unstated one-sided test. The negative correlation should therefore
  be treated as an exploratory observation from this dataset.

Finding these issues is part of the result. A repository about search integrity should not ask a
reader to trust its own evidence envelope.

## Reproduce the verifiable core

The default test suite is offline. Provider contracts use recorded fixtures; no API keys or live
calls are required.

```bash
python3 -m pip install -e '.[dev]'
python3 -m pytest -q
python3 -m ruff check .
python3 experiments/ds3/classify.py
```

Expected classification headline:

```text
exact                    38
alternate                 9
wrong                   214
all_corroborations      261
precision, STRICT         0.1456
```

The classification command reproduces the committed artifact, including the alternate-label
defect disclosed above.

## Read the record

| Artifact | What it contains |
|---|---|
| [`docs/DS3-DECISION.md`](docs/DS3-DECISION.md) | The decision written from the 60-query evaluation; retain the audit notes above while reading it |
| [`experiments/ds3/data/`](experiments/ds3/data/) | Raw provider output, scored queries, and classification output for n=22 and n=60 |
| [`docs/EXPERIMENT-OVERLAP.md`](docs/EXPERIMENT-OVERLAP.md) | The earlier overlap experiment and the defect it exposed |
| [`docs/CONCEPT.md`](docs/CONCEPT.md) | The original product hypothesis; preserved as historical context, not current product truth |
| [`docs/PROVIDERS.md`](docs/PROVIDERS.md) | Provider-index provenance and independence classes |
| [`core/`](core/) and [`tests/`](tests/) | Deterministic implementation through the pure-core stage and its offline tests |

## Status

**Research complete. Product development stopped.**

The valuable artifact is the decision trail: a plausible trust mechanism was made falsifiable,
implemented deterministically, tested against labelled data, rejected on its measured precision,
and then audited hard enough to expose weaknesses in the evaluation itself.
