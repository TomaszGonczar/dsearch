# Historical Antecedent Artifact (Omega-v3 Search Router)

This directory preserves the original 575-line search router implementation from `Omega-v3` (`core/lib/search_router.py`), referenced in [`docs/CONCEPT.md` §10](file:///Users/tomaszgonczar/dsearch/docs/CONCEPT.md#L480-L486).

## Role in the dSearch Falsification Study

This artifact represents the **pre-evaluation state**:
1. **The Heuristic:** In `search_router_v1.py` (lines 284–292), multi-engine overlap was naively promoted as a trust signal:
   ```python
   entry.consensus = len(entry.providers) > 1
   sorted_items = sorted(fused_map.values(), key=lambda x: (1 if x.consensus else 0, x.score), reverse=True)
   ```
2. **The Investigation:** `dSearch` was created to test whether this assumption held true against ground-truth document retrieval across 60 labelled queries.
3. **The Outcome:** The study measured strict precision at **0.1456** (Wilson 95% CI [0.108, 0.194]), proving that agreement across search engines does not correlate with document ground-truth.
4. **The Decision:** Development of a production backend, MCP server, and CLI based on this consensus heuristic was terminated. This router is preserved as empirical evidence of the hypothesis before falsification.
