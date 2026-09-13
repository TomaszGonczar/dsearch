# Choosing your providers

> [!WARNING]
> Historical design reference. The explicit independence classes remain part of the retained
> provider configuration, but no router was shipped and cross-provider agreement did not validate
> as a quality signal. Pairing advice below is not current product guidance; see the
> [README](../README.md).

**This document is half the product.** The router is the machinery; this is the map of what
to plug into it, and — more importantly — **what not to pair**.

The routing engine is deterministic and provider-agnostic. Its trust signal, however, depends
entirely on one property of the providers you choose: **index independence**. Pick wrong and
the consensus mark becomes decoration.

---

## The one rule that matters

> **Consensus requires at least two genuinely independent indexes.**
>
> Two providers that derive results from the same upstream index will agree on almost
> everything. That agreement carries zero information — it is one opinion, counted twice, and
> wearing a badge that says "confirmed by two sources."

Everything below exists to help you avoid exactly that mistake.

---

## Independence classes

| Class | What it means | Consensus value |
|---|---|---|
| **A — Independent** | Operates its own crawler and its own index. Coverage gaps differ from every other provider's. | **Full.** This is what consensus is for. |
| **B — Aggregator** | Own crawler *plus* licensed third-party data. Partly independent, partly derivative — and you cannot tell which part answered your query. | Partial and **non-deterministic**. Pairs badly with itself. |
| **C — Derivative** | Reseller of someone else's index (Google, Bing). Identical coverage to every other reseller of the same upstream. | **None.** Two class-C providers are one provider. |

**Mixing rule:** a consensus mark is only trustworthy when **both** contributing providers are
class A. The router does not attempt to guess a provider's class — that is a configuration
decision, and this document is the reference for making it.

---

## Provider table

Free-tier figures are as reported by the providers or their comparison pages at the time of
writing. **Verify at signup** — these change, and a guide that silently goes stale is worse
than no guide. Where sources conflict, both are shown.

### Class A — independent (use these for consensus)

| Provider | Index | Retrieval | Free tier | Verified |
|---|---|---|---|---|
| **Brave** | Own crawl, first-party. Reported ~30B pages, ~100M daily updates. Explicitly **not** Google-derived. | Keyword, conventional ranking | ~$5 credit/month reported | ✅ provider + third-party |
| **Exa** | Own proprietary **neural/embeddings** index over a curated crawl. Reported to be "a fraction of the size of Brave's" — a smaller but *differently-shaped* index. | Semantic embedding similarity | Reported free monthly allowance (figures conflict: 250 vs 1k) | ✅ provider + third-party |
| **Parallel** | Own web-scale index, "billions of pages, millions added or updated daily". Built for agents; supports live crawl for time-sensitive queries. | Objective + query, agent-optimised | Not verified — check at signup | ✅ provider (index claim) |

All three are class A. Their **coverage gaps differ**, which is the entire point — Brave misses
what Exa has, Exa misses what Brave has, and neither can tell you which.

### Class B — aggregator

| Provider | Index | Why it is class B | Verified |
|---|---|---|---|
| **Tavily** | Own crawler **+ licensed third-party data** | You cannot know whether a given result came from its crawler or from upstream aggregation — so its independence varies per query and cannot be reasoned about. | ✅ third-party analysis (Brave's comparison) + Tavily's own "aggregates up to 20 sites per call" |

Tavily is a good product and a fine *single* provider. It is a weak **consensus partner**,
because its independence is not a fixed property you can depend on.

### Class C — derivative (never pair two)

| Provider | Upstream | Note |
|---|---|---|
| Google Custom Search JSON API | Google | Official, narrow, compliant — but Google's index |
| SerpAPI / Serper / similar | Google | Same upstream coverage as each other |
| Bing-backed resellers | Bing | Same upstream coverage as each other |

Two class-C providers from the same upstream agree because they **are** the same index. Using
them together produces a confident-looking consensus that means nothing. The router cannot
detect this for you: from its side, they look like two providers.

---

## Recommended pairings

### The default — two class A indexes

```
Brave  +  Exa
```

**Why this pair.** They differ on *both* axes that matter:

| | Brave | Exa |
|---|---|---|
| Index | Own crawl, keyword-oriented | Own neural index, meaning-oriented |
| Retrieval | Keyword match | Embedding similarity |
| Failure mode | Misses paraphrases | Misses exact-token lookups |
| Coverage gap | Different pages | Different pages |

They disagree for *different reasons*. When they nonetheless surface the same canonical URL,
that is a strong signal — one is keyword evidence, the other semantic evidence, over two
independent crawls. A pair that differs on only one axis gives a weaker mark.

This is the recommended starting point, and both have a free tier sufficient for individual
use.

### The agent-native alternative

```
Brave  +  Parallel
```

Already implemented in the source this project extracts from. Parallel's index is built for
agent queries and supports live crawls for time-sensitive lookups; Brave supplies the
independent second opinion. Choose this over Brave+Exa if your queries lean toward
freshness-sensitive agent tasks rather than document discovery.

### Do not use

```
Tavily + <anything>          # class B partner: independence is not fixed
Google + SerpAPI             # both class C, same upstream — consensus is theatre
Serper + SerpAPI             # same upstream again
```

---

## Tier recommendation

Free-tier figures are enough for individual use. **Two keys is the product.**

```
Tier 2  — RECOMMENDED        two class-A keys        → RRF fusion + consensus    ⭐
Tier 3  — for data nerds     two keys + rerank key   → cross-encoder over candidates
```

| Tier | Keys | What you get | Who it is for |
|---|---|---|---|
| **2** | 2 | **The product.** Independent-index consensus, attributed envelopes, bounded timeouts | Everyone. This is the recommendation. |
| **3** | 3 | Tier 2, plus a cross-encoder reranking the fused candidates | People who want to argue about ranking quality, not availability |

Tiers 0 and 1 exist — the tool works with zero or one key and says `degraded` — but they are
**not the product**. They fix the loud failures (silent empty, stall). Only Tier 2 fixes the
quiet one, and the quiet one is why this exists.

### The rerank key, if you go Tier 3

A cross-encoder over already-fused candidates. Cohere's `rerank` is the reference
implementation; the engine also ships a **deterministic local fallback** (TF cosine, stdlib,
no key), so Tier 3 degrades to something honest rather than to nothing.

Reranking changes *ordering*. It does not change *membership* or *truth* — the consensus marks
were computed before rerank and remain valid afterwards. Worth knowing before you assume the
reranker is doing more than it is.

---

## Notes for contributors

- **Never hardcode the provider list.** The engine is provider-agnostic and the table above is
  data, not code. New class-A providers should be addable without touching routing logic.
- **Never infer independence from an API shape.** Two providers exposing identical JSON do not
  share an index, and two exposing different JSON might. Independence is a claim about
  crawlers, and it belongs in configuration with a source, not in a heuristic.
- **Record the class in the config, not in a comment.** A provider's class is load-bearing at
  runtime: it decides whether a consensus mark is emitted at all.
- **Re-verify the free tiers periodically.** A stale "free" claim sends a user to a signup page
  that wants a credit card. Mark figures with the date they were checked.
