# search-router

**Portfolio #2 — a search reliability and trust layer for coding agents.**

> Dear developer — how many searches have been corrupted in your coding agent?
>
> Not failed. **Corrupted.** A search that returned nothing, said nothing about returning
> nothing, and let your agent plan on top of it.
>
> Can you count them? I couldn't. That is the problem.
>
> A failed search is visible. A *silently empty* search is indistinguishable from a good one,
> and your agent treats both the same. Every corrupted search quietly degrades the research
> phase, and the plan built on it, and the code built on the plan.
>
> `search-router` exists because I got tired of not being able to count them.

---

## The one-paragraph version

Every coding agent ships a web search tool, and it fails in the worst possible way:
successfully. A real documented Claude Code session returned `{"results": [], "searchCount":
0}` three times in a row — including one call that took **264 seconds** — while handing the
model a result envelope that said *"REMINDER: You MUST include the sources above in your
response."* The agent did not error. It reasoned on top of nothing.

`search-router` treats search as a **trust problem**, not an availability problem. It queries
engines with independent indexes in parallel under a hard timeout, fuses their rankings with
Reciprocal Rank Fusion, and marks which results two independent sources agree on. Zero results
is never a null — it is an attributed outcome naming which providers were asked and why each
failed.

## Three failures it addresses

| # | Failure | Why it is worse than an outage | What the router does |
|---|---|---|---|
| 1 | **The Silent Empty** — HTTP 200, zero results | An outage is loud. An empty set is *epistemically invisible*: the model cannot tell it is reasoning from nothing, and neither can you | Every response is an attributed envelope. Empty is a first-class outcome, never a null |
| 2 | **The Single-Index Blind Spot** — the page is not in *this* index | Results look fine: credible titles, real domains, plausible snippets. Nothing suggests the authoritative page exists elsewhere | RRF fusion over independent indexes; `consensus: true` when 2+ agree on the same canonical URL |
| 3 | **The Stall** — the call hangs | It does not abort. Documented: 264 s on one call, then 158 s of silence until a human interrupted | Per-provider timeout, parallel fan-out. A hung provider cannot eat the research phase |

## Three claims, each verifiable

1. **Never a silent empty.** Attributed envelopes at every tier.
2. **Agreement is measurable.** Deterministic consensus marking. No model in the trust path.
3. **Bounded by construction.** Timeout per provider, explicit failover chain, honest
   `degraded` tier when keys are absent.

## Two signups, not four

The setup objection is fair, and the answer is tiers — the product is **Tier 2**, not Tier 4:

```
Tier 0  no keys           → works, labelled degraded
Tier 1  one free key      → bounded search, attributed envelope   (fixes #1 and #3)
Tier 2  two free keys     → RRF fusion + consensus  ⭐ THE PRODUCT
Tier 3  + rerank key      → cross-encoder over candidates          (for data nerds)
```

**Two free API keys gets the whole product.** Brave ships monthly free credit on its own
independent index; Exa and Tavily both have free monthly allowances.

### But it has to be the *right* two

This is the part that makes the project more than a router, and it is why a provider guide
ships with the engine:

> Two providers deriving results from the same upstream index agree on almost everything.
> That agreement carries zero information — it is one opinion counted twice, wearing a badge
> that says "confirmed by two sources."

**Tavily is an aggregator**, not an independent index — Brave's own comparison describes it as
using "its own crawler in tandem with third-party data aggregation." Pairing Brave with Tavily
*looks* like consensus and is not. A router cannot detect that. So the guide does:

```
✅  Brave + Exa          two independent indexes, differing on BOTH axes
                        (keyword crawl vs neural index, different coverage gaps)
✅  Brave + Parallel     the agent-native alternative
❌  Tavily + anything    aggregator — independence varies per query
❌  Google + SerpAPI     both derivative of the same upstream — consensus is theatre
```

→ **[`docs/PROVIDERS.md`](docs/PROVIDERS.md)** — independence classes, free tiers with
verification sources, recommended pairings, and the combinations to avoid.

An engine that returns a confidence signal, shipped without a map of which providers make that
signal meaningful, hands the user a number they cannot interpret. The guide is what turns
`consensus: true` from decoration into evidence.

## What is not new, and what is

Multi-provider fallback exists — `reliable-web-search`, **AllSearch MCP**, and several others do
it well. That solves *"can I get an answer?"*

Nobody ships the second question: *"should I trust this answer?"*

```
AllSearch MCP:   more providers → better answer      (Grok-first, model in the loop)
reliable-web-search:  provider A down → use B        (failover only)
search-router:   measured agreement → known trust    (no model in the path)
```

The sharpest difference: **AllSearch's "independent cross-validation" is computed across a
model's citations × an aggregator's results.** Tavily is not an independent index — it uses
"its own crawler in tandem with third-party data aggregation." So its cross-provider hits mean
*"a model said this and an aggregator found it,"* which is materially weaker than *"two
independent crawlers found it"* — and a router cannot tell the difference, because it never
asks what an index **is**. That is why [`docs/PROVIDERS.md`](docs/PROVIDERS.md) exists.

### The mechanism nobody else has: disagreement as output

Every merge-and-rank pipeline treats disjoint result sets as a merge problem — union and sort.
That destroys the most informative outcome available:

```
[search-router] vercel.json schema validation

⚠ NO CONSENSUS — 0 of 8 results confirmed by both indexes
  brave: 5 results · exa: 5 results · overlap: 0
  → independent indexes agree on nothing.
    treat as: ambiguous query, or contested topic. Verify before planning.
```

When two independent indexes return nothing in common, that is a **finding** — the query is
ambiguous, the topic is contested, or one index has a gap. A Grok-first pipeline and a
merge-first pipeline are both structurally committed to producing something coherent, so
neither can report that the evidence does not cohere. An auditor can.

## Where a competitor beats us, stated plainly

An honest review of [AllSearch MCP](docs/COMPETITIVE.md) found six things they shipped that we
had specified badly or not at all — context-usage-aware budgets, SSRF-hardened fetch, hard
total deadlines, stateful circuit breakers, depth-by-intent naming, and strict-mode refusal.
**All six are adopted, with credit.**

They are also ahead on execution by a wide margin: working code, offline test suite, a shipped
Pi extension. We have four markdown files and no repository. That is the honest headline, and
the competitive document says so.

## Installable in any coding agent

One engine, per-agent adapters — same architecture as Portfolio #1, because the user is
**inside** their agent, not at a terminal.

| Surface | Agents |
|---|---|
| **MCP server** (stdio) | Claude Code, Codex, OMP, agy, Cursor, Windsurf, VS Code, Gemini CLI, OpenCode |
| **Native extension** | OMP / pi — in-process |
| **Terminal binary** | CI, scripting, unintegrated agents |

Two integration patterns:

- **Additive** — expose the router as a new tool beside the agent's default. Simple; the model
  must *choose* it, and it does not know its default search is lying.
- **Corrective** — wrap the agent's *existing* `web_search` so the default path routes through
  the router. The model cannot choose wrong, because there is no longer a wrong path. This is
  where the product stops being a nicer search API.

## Status

Design phase. No code, no repository yet.

- [`docs/CONCEPT.md`](docs/CONCEPT.md) — the full concept: failure scenarios, competitive
  position, tiering, adapter model, decisions and open questions
- [`docs/PROVIDERS.md`](docs/PROVIDERS.md) — **which providers to use and which never to pair**
- [`docs/DIAGRAMS.md`](docs/DIAGRAMS.md) — architecture, failure flows, trust model
- [`docs/COMPETITIVE.md`](docs/COMPETITIVE.md) — **AllSearch MCP compared, in both directions**

Source material for extraction: `Omega-v3/core/lib/search_router.py` (575 lines) — dual-engine
ensemble, RRF with URL canonicalization, Exa failover, two-layer rerank.

## License

MIT (to be confirmed).
