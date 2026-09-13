# dSearch

**Archived research report. Development stopped before an end-to-end search product existed.**

dSearch tested whether a URL returned by more than one independent search index was more likely
to be the right page for a query.

Four providers were queried for 60 document-finding queries. Consensus was calculated across the
eligible independent indexes. Of 261 URLs returned by at least two of those indexes, 38 matched a
labelled reference URL. Strict precision was **0.1456** (Wilson 95% CI **[0.108, 0.194]**).

The measured precision was too low to use agreement as a quality signal. This repository contains
the pure-core implementation, recorded provider output, evaluation scripts, and a later audit of
the experiment.

[Results](#results) · [Method](#method) · [Decision](#decision) ·
[Limitations](#limitations-found-in-review) · [Reproduction](#reproduction)

## Results

| Question | Result |
|---|---|
| How often did a corroborated URL match the labelled page? | **38 / 261 = 0.1456** |
| Did a zero-consensus case identify ambiguous queries? | No zero case occurred; consensus fired in **60 / 60** evaluation queries |
| Was greater agreement associated with greater precision? | An exploratory inclusive analysis found a negative association: **r = -0.287**, two-sided **p = 0.026** |

Search indexes tend to share coverage of popular pages such as documentation roots, repository
pages, and general references. Several providers can return those pages even when a query asks
for one specific reference.

The decision rests on the strict result: 38 exact matches among 261 corroborated URLs. The
negative correlation is exploratory because its calculation has the classification and
provenance limitations described below.

## Why this was tested

The project began with a failure observed in an agent session. Three web searches returned no
results without producing a useful failure for the model. One call took 264 seconds. The agent
continued planning without search evidence.

dSearch separated two concerns:

1. Search should return an attributed, bounded outcome, including when no results are found.
2. Agreement between independent indexes might provide evidence that a result is reliable.

The deterministic envelope addresses the first concern. The second claim motivated the router,
so it was evaluated before provider orchestration and agent integrations were implemented.

## Method

- 60 queries asking for specific technical documents.
- One or more labelled reference URLs per query.
- Four providers, with up to 10 results requested from each.
- Consensus calculated only across providers configured as independent.
- URL comparison after normalizing scheme, `www`, trailing slashes, and tracking parameters.
- A URL classified as corroborated when at least two eligible providers returned it.
- Strict precision defined as exact canonical matches divided by all corroborated URLs.

The first run contained 22 queries:

```text
12 exact matches / 108 corroborated URLs = 0.1111
Wilson 95% CI: [0.065, 0.184]
```

The extended run contained 60:

```text
38 exact matches / 261 corroborated URLs = 0.1456
Wilson 95% CI: [0.108, 0.194]
```

Raw responses, per-query scores, and classifications for both runs are in
[`experiments/ds3/data/`](experiments/ds3/data/).

The unit of measurement is page retrieval. The experiment checks whether consensus recovers a
labelled document; it never evaluates an answer produced from the search results.

## Decision

At 0.1456 strict precision, consensus remains descriptive metadata. It provides no evidence that
a page is correct or relevant.

Rescuing consensus with a semantic relevance model would put an opaque judgement inside the path
intended to provide auditable evidence. Development stopped instead.

Development stopped after this result. The repository is retained as the record of the test and
the decision.

The implemented parts are:

- attributed envelopes with explicit zero-result outcomes;
- URL canonicalization;
- pairwise agreement calculations;
- context-aware output budgets;
- provider declarations and offline contract fixtures;
- handling for malformed provider URLs;
- 78 offline tests for the provider contracts and pure core.

Implementation ends at the pure core. The provider orchestrator, command-line product, MCP
server, and supported package were never built.

## Limitations found in review

A separate verification pass reproduced the strict precision result and found three problems
with the broader analysis:

- **Alternate classifications.** [`classify.py`](experiments/ds3/classify.py) counts two URLs as
  `alternate`, although their annotations say they should remain `wrong`. The committed inclusive
  precision is 0.1801; applying the stated conservative rule gives `45 / 261 = 0.1724`. Strict
  precision remains 38 / 261 because it excludes every alternate.
- **Label chronology.** Measurement timestamps precede the commits that first contain the
  corresponding labels, and the label metadata timestamps are later still. The repository
  cannot establish the claimed ordering or rule out labels informed by provider output.
- **Missing evidence and analysis code.** The overlap summary omits the provider URLs and repeated
  calls needed to recompute its pairwise Jaccard and stability claims. Its document records
  Parallel repeat stability at `J = 0.82`, not `1.00`. The permutation, median-split, and
  domain-precision calculations were not committed as code, and their reported p-values require
  an unstated one-sided test.

The negative correlation is therefore an exploratory result from this dataset.

## Reproduction

The core test suite and stored classification run offline. No provider credentials are required.

```bash
python3 -m pip install -e '.[dev]'
python3 -m pytest -q
python3 -m ruff check .
python3 experiments/ds3/classify.py
```

Current output:

```text
78 passed
All checks passed!

exact                    38
alternate                 9
wrong                   214
all_corroborations      261
precision, STRICT         0.1456
```

The classification command reproduces the committed classification, including the two
alternate-label inconsistencies noted above. It does not independently reproduce every
statistical claim.

## Repository guide

| Path | Contents |
|---|---|
| [`docs/DS3-DECISION.md`](docs/DS3-DECISION.md) | Decision recorded after the 60-query evaluation |
| [`experiments/ds3/data/`](experiments/ds3/data/) | Provider output and scoring data for both runs |
| [`docs/EXPERIMENT-OVERLAP.md`](docs/EXPERIMENT-OVERLAP.md) | Initial overlap experiment |
| [`docs/CONCEPT.md`](docs/CONCEPT.md) | Original product proposal; not the current project status |
| [`docs/PROVIDERS.md`](docs/PROVIDERS.md) | Provider provenance and independence classes |
| [`core/`](core/) | Pure deterministic components |
| [`tests/`](tests/) | Offline tests |
