# AGENTS.md — rules for an archived research record

This repository is closed to product development. It records a search-consensus hypothesis,
the deterministic components built to test it, the measurements that falsified it, and the
limitations found during audit. It is not a supported search router or an installable agent
integration.

## Read in this order

1. `README.md` — current result, scope, limitations, and reproduction steps
2. `docs/DS3-DECISION.md` — the decision made from the 60-query evaluation, with an archival
   warning for claims weakened by the later audit
3. `experiments/ds3/data/` and `experiments/ds3/classify.py` — raw provider output and the
   reproducible strict-precision calculation
4. `docs/EXPERIMENT-OVERLAP.md` — the preliminary independence experiment and its evidence
   limitations
5. `docs/CONCEPT.md`, `docs/PROVIDERS.md`, `docs/COMPETITIVE.md`, and `docs/DIAGRAMS.md` —
   historical design documents, not descriptions of a current product

## Current findings

- Strict consensus precision is `38 / 261 = 0.1456` on 60 labelled document queries. This is
  the primary result and is reproduced by `experiments/ds3/classify.py`.
- The committed classifier reports nine alternate URLs. Two of those classifications conflict
  with their annotations; applying the stated conservative policy leaves seven. Strict
  precision is unaffected.
- The negative correlation between agreement rate and inclusive precision is exploratory. The
  classification issue affects its input, and the statistical analysis code was not committed.
- Repository history does not establish that labels predated provider calls. Do not state that
  chronology as proven.
- The preliminary overlap artifact does not contain enough raw data to reproduce every reported
  Jaccard and repeat-stability claim independently.
- Consensus remains descriptive metadata in the retained core. It must not be presented as a
  trust, relevance, correctness, or confidence signal.

## Evidence rules

1. Preserve raw result files and both the 22-query and 60-query evaluations. Do not rewrite data
   to make a document internally consistent.
2. Treat every document, comment, and generated classification as a claim to verify against the
   raw artifacts. Report contradictions explicitly.
3. Keep strict precision separate from inclusive precision. State the numerator, denominator,
   aggregation method, and classification policy with every derived figure.
4. Do not infer missing provenance. Unknown label chronology or missing analysis code stays
   unknown.
5. Keep historical documents legible as historical records. Put corrections in their archival
   warning or in a new audit note; do not silently normalize the original account.
6. Do not run live provider experiments as routine verification. Existing live responses are
   evidence snapshots and may contain provider-specific irregularities.

## Engineering rules

- The retained core is deterministic: no clock, locale dependence, unordered output, network
  access, or model judgement in the result path.
- Zero results is an attributed outcome with a cause, never a null or unqualified success.
- Provider independence classes are explicit configuration data and are never inferred.
- Tests run offline and provider contracts use recorded fixtures. A maintenance change that adds
  a failure path must add a test for it.
- Do not add runtime orchestration, a ledger, CLI, MCP server, agent adapters, or release
  packaging unless a human explicitly reopens the repository and defines a new tested premise.
- Do not add a model to rescue topical relevance or consensus quality. That would test a
  different system from the one recorded here.
- Do not commit API keys, `.env` files, or personal query data.

## Validation

Run from the repository root:

```bash
python3 -m pip install -e '.[dev]'
python3 -m pytest -q
python3 -m ruff check .
python3 -m mypy core providers scripts
python3 scripts/check_dependency_policy.py
python3 experiments/ds3/classify.py
```

The default suite must pass without network access. The classification command intentionally
reproduces the committed artifact, including the disclosed alternate-label defect.

## Changes to the archive

Prefer small commits that reduce ambiguity or improve reproducibility. Use conventional commit
subjects such as `docs(archive): clarify evaluation provenance`. In the commit body, state
whether raw evidence changed. If code and measurement disagree, stop and report the discrepancy;
do not adjust the measurement to fit the code.
