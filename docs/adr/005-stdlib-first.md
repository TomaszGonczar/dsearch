# ADR 005 — Use the standard library first

**Status:** Accepted
**Date:** 2026-09-13
**Deciders:** Operator
**Affects:** runtime dependencies, provider transports, serialization

## Context

dSearch sits in an agent's trust path. Each runtime dependency expands its supply-chain and
failure surface. The first provider APIs require only HTTP and JSON capabilities already
available in Python's standard library.

## Decision

The v0.1 runtime dependency allowlist is empty. HTTP transport uses `urllib`; serialization,
hashing, URL parsing, deadlines, and local persistence use standard-library modules. Adding a
runtime dependency requires a new ADR and an explicit allowlist change. CI rejects both an
unapproved dependency declaration and imports of common third-party HTTP clients.

## Consequences

The implementation accepts some extra adapter code in exchange for a smaller trusted base.
Development-only tools such as pytest, ruff, and mypy remain permitted.
