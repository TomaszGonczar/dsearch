# search-router — Concept

**Portfolio #2. Status: concept. No code, no repo yet.**

---

## The hook

> Dear developer — how many searches have been corrupted in your coding agent?
>
> Not failed. **Corrupted.** A search that returned nothing, said nothing about returning
> nothing, and let your agent plan on top of it.
>
> Can you count them? I couldn't. That is the problem. A failed search is visible; a
> *silently empty* search is indistinguishable from a good one, and your agent treats both
> the same. Every corrupted search silently degrades the research phase, and the plan built
> on it, and the code built on the plan.
>
> `search-router` exists because I got tired of not being able to count them.

---

## 1. The failure nobody instruments

Every coding agent ships a web search tool. It is the least examined component in the stack,
and it fails in the worst possible way: **successfully**.

Here is a real, documented Claude Code failure. Three searches, same session:

| Call | Duration | Result |
|---|---|---|
| WebSearch 1 | 2.26 s | **0 results** |
| WebSearch 2 | 1.74 s | **0 results** |
| WebSearch 3 | **264.42 s** | **0 results** |

The tool result the model received was not an error. It was this:

```
Web search results for query: "<query>"

REMINDER: You MUST include the sources above in your response to the user using markdown hyperlinks.
```

The underlying JSON was `{"results": [], "searchCount": 0}`.

**Read that again.** The agent is handed an empty result set, plus an instruction to cite
sources from it. It does not error. It does not retry. It does not tell the user. It proceeds
to reason about a query it never answered, and it will cite nothing while believing it
searched.

This is not one bug. It is at least four separate upstream reports of the same shape:
[#43744](https://github.com/anthropics/claude-code/issues/43744) (empty results),
[#27831](https://github.com/anthropics/claude-code/issues/27831) (`Did 0 searches`),
[#68421](https://github.com/anthropics/claude-code/issues/68421) (empty envelope **inside
subagents**), [#38866](https://github.com/anthropics/claude-code/issues/38866) (hangs
requiring manual interruption, "nearly every session involving web research with 3+
consecutive searches"). The third one matters most: it happens in **subagents**, which is
exactly where a fleet does its research, and where nobody is watching.

## 2. Three negative scenarios

Each scenario is drawn from a documented failure or a structural property of single-provider
search. Each ends with what `search-router` does differently.

---

### Scenario 1 — The Silent Empty

**What happens.** The provider returns HTTP 200 with an empty result set. The agent's tool
wrapper does not treat an empty envelope as an error, because it is not one — it is a valid
response containing nothing. The model receives "here are your search results" backed by
zero results, and continues.

**Why it is worse than an outage.** An outage fails loudly. The agent knows, the user knows,
the retry happens. A silent empty is *epistemically invisible*: the model has no signal that
it is now reasoning from nothing, and neither do you. In a chain of 5 searches, one silent
empty can quietly invalidate the planning step that depended on it — and there is no artifact
anywhere that says so.

**What search-router does.** It never returns a bare empty list. Every response carries an
explicit envelope:

```json
{
  "providers_attempted": ["parallel", "brave"],
  "providers_succeeded": [],
  "errors": { "parallel": "...", "brave": "..." },
  "total_results": 0,
  "consensus_count": 0
}
```

Empty is a **first-class outcome with attribution**, not a null. The caller can distinguish
three states that the default tool collapses into one: *nobody answered*, *somebody answered
with nothing*, and *somebody answered with results*. A caller that wants to fail closed can;
a caller that wants to escalate to a second engine can; and either way the fact is recorded.

---

### Scenario 2 — The Single-Index Blind Spot

**What happens.** One index does not contain the page you need. Not a failure — a gap. Brave
crawls its own index; Exa does semantic retrieval; Parallel optimizes for agent queries.
Their coverage overlaps but is not identical. A query that lands in a gap returns a
confident, well-formed, *wrong* result set: plausible pages that are not the answer.

**Why it is worse than an outage.** The result set looks fine. Titles are relevant, snippets
read well, the domain names are credible. Nothing indicates that the authoritative page
exists and simply was not in this index. The agent proceeds with the second-best answer and
treats it as the answer.

**What search-router does.** It queries engines whose indexes are *independent* and fuses
their rankings with Reciprocal Rank Fusion, then marks agreement explicitly:

```
⭐ Consensus (2+ sources): 3 results

1. <result>  [CONSENSUS ⭐]
   Źródło: parallel+brave | Score: 0.0317
```

`consensus: true` means two independent indexes surfaced the same canonical URL. That is a
**cheap, deterministic proxy for confidence** — not a model's opinion, not a relevance score
from a vendor that grades its own homework. And it works in the opposite direction too: when
nothing reaches consensus, the result set is marked as single-source, which is exactly the
signal you want before treating it as settled.

Before fusing, URLs are canonicalized (tracking params stripped, `www.` normalized, case
handled), so agreement is detected on the *page*, not on the vendor's URL decoration. Without
that step, three engines returning the same page look like three different results.

#### The inverse signal: disagreement is an output, not a failure to merge

A fusion pipeline treats disjoint result sets as a merge problem — union them and rank. That
**destroys the most informative outcome available.**

When two independent indexes return *nothing in common*, that is not a gap in the pipeline.
It is a finding:

- the query is ambiguous and the indexes interpreted it differently
- the topic is contested and they surface different camps
- one index has a coverage gap for this domain

None of those is expressible as a ranked list, and every merge-and-rank tool silently discards
them. So dcompact's sibling emits it:

```
[search-router] vercel.json schema validation

⚠ NO CONSENSUS — 0 of 8 results confirmed by both indexes
  brave: 5 results · exa: 5 results · overlap: 0
  → independent indexes agree on nothing.
    treat as: ambiguous query, or contested topic. Verify before planning.
```

This is the one mechanism no comparable tool has. A model-first pipeline (`answer` from Grok)
and a merge-first pipeline (union + rank) are both **structurally committed to producing
something coherent** — neither can report that the evidence does not cohere. An auditor's job
includes saying exactly that.

Agreement is reported as a continuum, not a boolean:

| Overlap | Signal | Meaning |
|---|---|---|
| High | `consensus: strong` | Independent crawlers corroborate — plan on it |
| Partial | `consensus: partial` | Some items confirmed, some single-source |
| **None** | `consensus: none` ⚠ | **Contested or ambiguous — do not plan on this** |
| One provider only | `consensus: unavailable` | Honest: no second opinion was obtained |

---

### Scenario 3 — The Stall

**What happens.** A search call hangs. Not fails — hangs. In the documented case: 264 seconds
on the third call, then the top-level request sat silent for another 158 seconds until the
user interrupted manually. Total ~7 minutes of a research phase consumed by one query.

**Why it is worse than an outage.** It does not abort. An agent doing 3-5 sequential searches
(as the report describes: "nearly every session involving web research with 3+ consecutive
searches") has no budget for one call to eat seven minutes. Worse, it happens *more* often at
high context usage — precisely when a long research run is deepest in its work and least able
to afford a stall.

**What search-router does.** Per-provider timeout, enforced by construction:

```python
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
    future_map = {
        executor.submit(fn, query, max(count, 5), timeout): name
        for name, fn in targets
    }
```

Two engines queried **in parallel** under an 8-second default timeout each. The wall-clock
cost of the primary pair is the slower of two, not the sum. A hung provider cannot stall the
call — it is bounded, recorded in `errors`, and the other engine's results are returned.
`waterfall_search` exists for the cost-sensitive path where you would rather save queries
than have redundancy: it tries engines in sequence and stops at the first success.

---

### The pattern across all three

| | Default single-provider tool | search-router |
|---|---|---|
| Empty result | Indistinguishable from success | Attributed, with per-provider errors |
| Coverage gap | Invisible | `consensus` flag + single-source marking |
| Hang | Unbounded | Per-provider timeout, parallel execution |
| Retry | Model's job, if it notices | Automatic failover chain |
| Trust signal | Relevance score from the vendor | Agreement between independent indexes |

The through-line: **the default tool reports a result set. search-router reports the state of
the search.** Those are different products.

## 3. Does this already exist?

Honest answer: **partially, and the part that exists is not the part that matters.**

| Project | What it does | What it does not |
|---|---|---|
| [`reliable-web-search`](https://github.com/leecdiang/reliable-web-search) | Multi-provider fallback, circuit breaking, credential rotation, MCP server, 8 providers | No fusion, no consensus. Failover only: provider A fails → use B. 3 stars, 34 commits. |
| Multi-Search MCP Server | Unified search across Google/Tavily/DDG/Brave with automatic fallback | Same — a routing shim, single-result-set semantics |
| Firecrawl / Exa / Tavily MCP servers | One provider, well-integrated | Single-provider by definition |
| Vendor-native `web_search` | Built into the agent, zero setup | The problem being solved |

So the **availability** angle is occupied. The **epistemic** angle is not.

That distinction is the whole product:

```
reliable-web-search:  "provider A is down → use provider B"
                      → solves Scenario 3 (stall), partially

search-router:        "do independent indexes AGREE? and if they don't, say so"
                      → solves Scenario 1 (silent empty), 2 (blind spot), 3 (stall)
```

Fallback answers *"can I get an answer?"*. Consensus answers *"should I trust this answer?"*
The first is infrastructure. The second is the thing that silently corrupts research, and
nobody sells it.

## 4. What it actually is

**A search reliability and trust layer for coding agents.**

Three claims, each independently verifiable:

1. **Never a silent empty.** Every response is an attributed envelope. Zero results is an
   outcome with a cause, never a null.
2. **Agreement is measurable — and only when the indexes are independent.** Independent
   indexes fused with RRF; consensus marked deterministically. No model in the trust path.
   The engine enforces the mechanism; [`PROVIDERS.md`](PROVIDERS.md) tells you which
   provider choices make the signal real, and which quietly reduce it to one opinion worn
   twice.
3. **Bounded by construction.** Per-provider timeout, parallel fan-out, explicit failover
   chain. A hung provider cannot consume the research phase.

Plus one that makes it usable:

4. **Degraded mode is honest, not broken.** With zero API keys it still searches (a
   keyless provider), and says `tier: degraded` rather than pretending.

Plus the artifact that makes it a product rather than a library:

5. **A provider guide, because the trust signal depends on your choices.** Which providers
   have genuinely independent indexes, which are aggregators, which are derivative — with the
   verification behind each claim and the pairings to avoid. Most tools answer "which should I
   pick?" with a default. This answers with a reason.

### 4.1 Adopted from the competitive review

An honest comparison against a working competitor
([`COMPETITIVE.md`](COMPETITIVE.md)) produced six features they shipped that we had specified
badly or not at all. Adopted outright, with credit:

| Feature | Why it is better than what we had |
|---|---|
| **Context-usage-aware budget** — tighten the summary as the agent's context fills, not a flat cap | Ours was static. Theirs adapts to how full the context already is. |
| **SSRF-hardened `fetch`** — reject localhost/private IPs/embedded credentials, re-validate the *final* redirect URL, 0600 temp files | We had **no retrieval story at all**. This is a security surface we had not considered. |
| **Hard total deadline across all stages**, not per-provider only | Ours bounded one call; theirs bounds the operation, so a slow stage cannot eat the budget. |
| **Circuit breaker with state per provider** | Failover without memory retries a provider that has failed five times in a row. |
| **Depth by intent** — `fast` / `balanced` / `verify` / `deep` | Our `Tier 0–3` named *setup burden* (how many keys you bought). Nobody wants to reason about that. Intent is what a user actually chooses. |
| **Strict mode that refuses** rather than silently substituting | Already our principle; their naming is better and is adopted. |

### 4.2 The audit ledger is the headline, not a feature

Reading a well-built competitor settled open question 3 below. Their per-call diagnostics are
excellent — which providers ran, why, at what latency — and **nothing accumulates**. After a
week of use their user still cannot answer the question this project exists to ask:

> *"How many searches were corrupted? 14 searches, 3 empty, 2 single-source, 1 no-consensus."*

Per-call observability does not produce a rate. Without an accumulating local ledger, search
corruption stays unmeasurable **even with a strictly better search stack** — which means the
ledger is not an add-on to the product, it *is* the product's headline. A one-line-per-search
append to a local file, no network, same privacy posture as Portfolio #1.

## 5. What you set up — and it is two signups

The objection is fair: *"this needs Brave + Parallel + Exa + Cohere, nobody will do that."*
It needs **two**, and the product is explicitly tiered so that is the recommended — not
minimum — experience.

| Tier | Keys | You get | Who it is for |
|---|---|---|---|
| **0 — Degraded** | none | Keyless provider only. No consensus. Labelled `degraded`, not broken. | Trying it before signing up |
| **1 — Single** | 1 | Working search, bounded timeout, attributed envelope. Solves §2 scenarios 1 and 3. | One provider is enough for you |
| **2 — Consensus** ⭐ | **2** | **The product.** RRF fusion over independent indexes, consensus marking. Solves scenario 2. | **Everyone. This is the recommendation.** |
| **3 — Reranked** | 3 | Tier 2, plus a cross-encoder over fused candidates. | People who want to argue about ranking quality |

Two free API keys gets the whole product. Brave ships monthly free credit on its own
independent index; Exa and Tavily both have free monthly allowances.

The design rule: **never require N providers to function** — degrade the tier, keep the
contract. The envelope shape is identical at every tier, which is what lets one engine stay
portable across nine agents.

### The rule that makes consensus real

Tier 2 is not "any two providers." It is **two genuinely independent indexes**:

> Two providers deriving results from the same upstream index agree on almost everything.
> That agreement carries zero information — it is one opinion counted twice, wearing a badge
> that says "confirmed by two sources."

**This is why the repository ships a provider guide and not just an engine.**
[`docs/PROVIDERS.md`](PROVIDERS.md) classifies providers into independent / aggregator /
derivative, with the verification behind each claim, and names the pairings that work:

```
✅  Brave + Exa                 two independent indexes, differing on BOTH axes
✅  Brave + Parallel            the agent-native alternative, already implemented
❌  Tavily + anything           aggregator: own crawler + licensed third-party data,
                                so its independence varies per query
❌  Google + SerpAPI            both derivative of the same upstream — consensus is theatre
```

The finding that forced this document: **Tavily is not an independent index.** Per Brave's own
comparison, it "performs discovery using its own crawler in tandem with third-party data
aggregation." Pairing Brave with Tavily looks like consensus and is not. A router cannot detect
that — which is precisely why the guide is a first-class artifact rather than a footnote.

### Why the guide is part of the product

An engine that returns a confidence signal, shipped without a map of which providers make that
signal meaningful, hands the user a number they cannot interpret. The guide is what converts
`consensus: true` from a decoration into evidence.

It is also the honest answer to a question every user will ask: *"which ones should I pick?"*
Most tools answer that with a default. This answers it with a reason — and with the pairings to
avoid, which is the part nobody documents.

## 6. The default you did not audit

The underrated part is not that agent search is bad. It is that **agent search is unaudited**.

Developers will spend a week evaluating a model, benchmark a vector database, argue about
temperature — and never once ask what happens when their agent's `web_search` returns an
empty set. It is a single tool call, buried in a stack of dozens, treated as plumbing.

Why the blindness:

- **It is invisible by default.** No logging, no counters, no "searches: 14, empty: 3" line
  anywhere in any agent's output that I have found.
- **It is not in the failure taxonomy.** Teams instrument API errors, timeouts, rate limits.
  "Returned successfully with nothing" is not a category anyone writes a monitor for.
- **It compounds silently.** One empty search invalidates one planning step. You cannot see
  the invalidation — you see a plan that is subtly wrong three steps later and blame the
  model.
- **It is hidden inside subagents.** The documented empty-envelope-in-subagents report is the
  sharpest version: research fleets run in subagents, and a subagent's corrupted search never
  reaches the parent's context at all.

The result is an entire class of silent quality loss that no one measures, in the part of the
pipeline that everything downstream depends on. **You cannot fix what you do not count.**

## 7. Installation model — one engine, per-agent adapters

Same architecture as Portfolio #1, for the same reason: the user is **inside** their agent,
and the terminal is the fallback, not the interface.

```
                    search-router (one engine)
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
   MCP server          native extension      terminal binary
   (Claude, Codex,     (OMP: in-process)      (CI, scripting,
    Cursor, Windsurf,                           unintegrated)
    VS Code, Gemini,
    OpenCode, agy)
```

| Surface | Agents | Note |
|---|---|---|
| **MCP server** | Claude Code, Codex, OMP, agy, Cursor, Windsurf, VS Code, Gemini CLI, OpenCode | One stdio definition reaches nine agents |
| **Native extension** | OMP / pi | In-process; can wrap the agent's own search tool |
| **Terminal binary** | Any | For scripting and agents with no integration |

**Two integration patterns, and the second is the interesting one:**

1. **Additive** — expose `search_router` as a new tool beside the agent's default. The model
   *may* use it. Simple, non-invasive, weaker: the model chooses, and it does not know its
   default search is lying to it.
2. **Corrective** — where the agent exposes a tool-interception hook, wrap the *existing*
   `web_search` so the default path routes through the router. The agent does not have to
   choose correctly, because there is no longer a wrong path. This is where the product
   becomes more than a nicer search API.

Pattern 2 requires per-agent interception: `tool_call`/`tool_result` in OMP, `PreToolUse` in
Claude Code, whatever P4-equivalent recon finds for Codex. Same discipline as dcompact —
observe the surface, do not assume it.

## 8. Why it belongs in the portfolio

It is the same thesis as dcompact from a different angle: **the tooling agents depend on is
unaudited, and the failure modes are silent.**

- dcompact: the agent's memory is a paraphrase, and its loss is invisible.
- search-router: the agent's research is single-sourced, and its corruption is invisible.

Both answer with the same move: **make the invisible thing measurable, deterministically,
without putting a model in the trust path.** dcompact makes context loss countable.
search-router makes search corruption countable. Neither asks the user to trust a summary.

## 9. Decisions made, and open questions

### Settled

- **Tier 2 is the recommendation, Tier 3 the enthusiast tier.** Two class-A keys is the
  product; a third key buys ranking refinement, not new capability. See §5.
- **The provider guide is a shipped artifact, not documentation.** Because consensus is only
  meaningful across independent indexes, and because a router cannot detect a bad pairing, the
  classification and its verification ship with the engine. See [`PROVIDERS.md`](PROVIDERS.md).
- **The engine must record a provider's independence class at config time**, not infer it.
  Independence is a claim about crawlers; it cannot be read off an API response. Whether a
  consensus mark is emitted at all depends on it, so it is runtime data.
- **Rerank stays, at Tier 3 only.** It changes ordering, never membership — consensus marks are
  computed before it and remain valid after. The deterministic local fallback means Tier 3
  degrades honestly rather than to nothing. It does not make consensus redundant: one ranks,
  the other attests.

### Open

1. **Is corrective integration (wrapping the agent's own `web_search`) v1 or v2?** It is the
   differentiator — removing the wrong path rather than competing with it — but it is
   per-agent work and varies by host. Decide whether v1 ships additive-only.
2. **Which keyless provider for the no-key tier?** DuckDuckGo HTML and SearXNG are the
   candidates; both carry stability and terms-of-service questions that need settling before
   shipping anything that depends on them.
3. **How does the guide stay current?** Free tiers move. Does the provider table carry a
   verification date and a re-check ritual, or does it drift? A stale "free" claim sends a user
   to a page that wants a card — worse than no claim.
4. **Should we publish a provider-integrity check?** A small harness that runs the same query
   against a user's configured providers and reports their real overlap would make the
   independence classes *measured* rather than *cited*. It also turns `PROVIDERS.md` from a
   static document into a verifiable one. Cost: a few API calls on setup.

### Resolved by the competitive review

5. **Does the tool count?** **Yes — the ledger is the headline** (§4.2). A competitor with
   excellent per-call diagnostics and no accumulation still cannot answer *"how many searches
   were corrupted?"* Per-call observability does not produce a rate. The ledger is the critical
   path, not an add-on.
6. **Is the audit log more important than search quality?** **Yes, and the framing was wrong.**
   It is not either/or: search quality without a ledger is unmeasurable, and a ledger without
   honest quality signals records nothing worth counting. They are one product — the router
   produces the signal, the ledger makes it a rate.
7. **Does consensus make reranking redundant?** **No, and they are different kinds of thing.**
   Reranking changes *ordering*; consensus changes *trust*. Consensus is computed before rerank
   and remains valid after it. A reranker cannot manufacture agreement between independent
   indexes, and consensus cannot tell you which of two equally-confirmed results matches the
   query better. Keep both, in that order.

## 10. Source material

Existing implementation to extract from: `Omega-v3/core/lib/search_router.py` (575 lines) —
dual-engine ensemble, RRF fusion with URL canonicalization, Exa HTTP failover,
two-layer rerank (Cohere + deterministic local fallback), waterfall mode, provider adapters
for Parallel / Brave / Exa. Tests in `Omega-v3/tests/test_search_router.py`.

Documented failure evidence:
[cc-switch#5363](https://github.com/farion1231/cc-switch/issues/5363) (264 s + 158 s, 0
results, empty envelope) ·
[claude-code#43744](https://github.com/anthropics/claude-code/issues/43744) ·
[claude-code#27831](https://github.com/anthropics/claude-code/issues/27831) ·
[claude-code#68421](https://github.com/anthropics/claude-code/issues/68421) (subagents) ·
[claude-code#38866](https://github.com/anthropics/claude-code/issues/38866) (hangs)
