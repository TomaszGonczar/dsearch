# ADR 002 — No model in the trust path

**Status:** Accepted
**Date:** 2026-09-13
**Deciders:** Operator
**Affects:** result decoding, canonicalization, consensus, envelopes

## Context

dSearch must be able to reproduce and audit every equality judgement and trust mark. A model
would make those decisions probabilistic and would require the caller to trust the mechanism
that is supposed to provide the receipt.

## Decision

No language model may decide whether a provider succeeded, whether two results identify the
same page, whether consensus exists, or what trust label a result receives. Those decisions
are deterministic code over recorded inputs. A model may consume dSearch output, but it may
not create or alter the integrity verdict.

## Consequences

The trusted result path is reproducible and testable offline. Semantic equivalence that cannot
be established deterministically remains unknown rather than being guessed.
