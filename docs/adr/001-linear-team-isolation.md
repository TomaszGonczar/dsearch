# ADR 001 — Linear team isolation per project

**Status:** Accepted
**Date:** 2026-09-13
**Deciders:** Operator
**Affects:** both portfolios; all agent briefs; `tools/linear` in each repository

## Context

Two portfolios now exist side by side, each worked by the same agents:

| | dcompact | dSearch |
|---|---|---|
| Repo | `TomaszGonczar/dcompact` | `TomaszGonczar/dsearch` |
| Contains | Session continuity — records what an agent *did* | Search integrity — records how well it *searched* |
| Issue prefix | `OG-nn` | `DS-nn` |

They share an architecture (one engine, per-agent adapters, append-only local state, no model in
the trusted path), a tooling pattern, and — critically — **the same agents as implementers.**

The operator's stated concern: *"I'm afraid the LLMs are going to get lost inside one project /
two subprojects and may mix them."*

This is not hypothetical. It is the exact failure this portfolio's sibling exists to measure,
pointed at our own workflow. An agent asked to "implement the consensus feature" has no way to
know which project's consensus — and a wrong guess produces a plausible-looking artifact about
the other project's work.

## Decision

**One Linear team per project. No shared team, no sub-project nesting.**

```
Organization: TPG96
├── Team OG  "Omega"    →  dcompact portfolio, issues OG-nn
└── Team DS  "dSearch"  →  dSearch portfolio,  issues DS-nn
```

Project *names* may collide safely because the team key is the namespace. Both could have a
project called "Foundation" with no ambiguity.

### Why a team, not a project

| Option | Verdict |
|---|---|
| Two projects in one team | ✗ Issue keys stay `OG-nn` for both. An agent reading `OG-72` learns nothing about which repository it belongs to. This is the failure mode. |
| Sub-projects / parent+child | ✗ Linear has no nested projects. Even where hierarchy exists, the issue key is unchanged — the identifier still carries no project information. |
| **Separate team per project** | ✓ **The issue key becomes the namespace.** `DS-4` is unambiguously a different repository from `OG-56`, in a single token, visible in every commit, branch name, PR title, and prompt. |

The decisive property is that **the namespace travels with the identifier.** A branch named
`issue/ds-04-...` cannot be confused with `issue/og-56-...`. An agent that has been told "your
issues start with `DS-`" can detect its own confusion: if it finds itself reading `OG-`, it is
in the wrong repository.

### Enforcement in tooling

Each repository carries its own Linear tool with **the team key hardcoded as a default**:

```bash
DSEARCH_LINEAR_TEAM=DS    # in dsearch's tools/linear
DCOMPACT_LINEAR_TEAM=OG   # in dcompact's tools/linear
```

A brief for one project names its team. A tool run in the wrong repository resolves the wrong
project and the mismatch is visible in the issue key it returns.

### What agents are told

Every brief opens with the repository, the team key, and the issue range. Not as context, but
as a **precondition**: *"you are working in `dsearch`; your issues are `DS-nn`; if you are
reading a `OG-nn` issue, stop — you are in the wrong repository."*

This converts a silent confusion into a detectable one, which is the same principle both
products are built on.

## Consequences

### Positive

- The issue key is a complete, one-token answer to *"which project?"* — in commits, branches,
  PRs, prompts, and tool output.
- Cross-contamination becomes **detectable** rather than merely unlikely: an `OG-` key inside a
  `dsearch` session is a hard signal.
- Each team gets its own workflow states, labels, and views, so a dSearch board is not polluted
  by dcompact triage.
- Deleting or archiving one portfolio leaves the other untouched.

### Negative / accepted

- **Two boards to check.** Mitigated by `tools/linear next` per repository, and by agent briefs
  naming exactly one team.
- **Cross-project work needs an explicit pointer.** If a change in dcompact is required by
  dSearch work, it must be filed in the owning team and referenced by full key. That is a
  feature: the dependency is recorded rather than implied.
- **Team sprawl** if every small experiment becomes a team. Rule: a team is created per
  *repository*, not per idea. Two repositories, two teams.

### Neutral

- Projects within a team remain the unit of *delivery* (milestones, phases). The team is the
  unit of *namespace*. Both levels are used for what they are good at.

## Alternatives considered

**A single `PORTFOLIO` team with both boards.** Rejected: issue keys would be shared and carry no
project information, which is the exact confusion this ADR exists to prevent.

**Prefix conventions without team separation** (e.g. titling issues `[dsearch] ...`). Rejected:
titles are editable, greppable-wrong, and absent from the identifier. The namespace must be
structural, not conventional.

**Separate Linear workspaces.** Rejected: unnecessary billing and auth overhead; teams already
provide the isolation level needed, and both portfolios share one operator.

## Verification

- [ ] Team `DS` exists with key `DS`
- [ ] `tools/linear next` in the `dsearch` repository returns only `DS-nn` issues
- [ ] `tools/linear next` in the `dcompact` repository returns only `OG-nn` issues
- [ ] A brief that names the wrong team is caught by a fixture asserting the mismatch is
      visible in tool output
