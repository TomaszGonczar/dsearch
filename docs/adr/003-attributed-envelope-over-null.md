# ADR 003 — Return an attributed envelope instead of null

**Status:** Accepted
**Date:** 2026-09-13
**Deciders:** Operator
**Affects:** every public search response

## Context

An empty list collapses distinct outcomes: no provider answered, a provider answered with no
matches, or a provider failed after another succeeded. That ambiguity is the silent failure
dSearch exists to expose.

## Decision

Every search returns one stable envelope shape containing attempted providers, provider
outcomes, results, errors, and consensus measurements. Zero results is an explicit outcome
with a cause. Public APIs never use null or a bare list as the complete search response.

## Consequences

Callers can fail closed or degrade deliberately without interpreting absence. The envelope is
slightly larger, but every reported state is attributable and countable.
