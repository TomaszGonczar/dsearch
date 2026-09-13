# ADR 004 — Keep the audit ledger local and append-only

> [!WARNING]
> Historical design decision. The ledger was not implemented; product development stopped after
> the consensus hypothesis failed its precision evaluation. See the [README](../../README.md).

**Status:** Superseded — not implemented
**Date:** 2026-09-13
**Deciders:** Operator
**Affects:** future ledger implementation and diagnostics

## Context

Per-call diagnostics cannot answer how many searches were corrupted over time. The history is
sensitive and must remain inspectable and deletable by the user without a service dependency.

## Decision

The ledger is a local append-only file with one deterministic record per search. dSearch does
not upload ledger data or require telemetry. Deleting the file deletes the complete history.
Existing records are never edited in place.

## Consequences

Aggregate rates can be derived from the same evidence the user owns. Concurrency and partial
writes will need explicit handling when the ledger is implemented.
