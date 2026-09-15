#!/usr/bin/env python3
# pyright: reportExplicitAny=false, reportAny=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnusedCallResult=false
"""Unified Federated Search Router — Dual-Engine Ensemble & Waterfall.

Zapewnia redundancję i wysoką jakość danych dla agentów (scout-agent, analyst-agent)
poprzez równoległe zapytania do niezależnych silników (Parallel + Brave) z fuzją
rankingową (Reciprocal Rank Fusion) i automatycznym failoverem na Exa-HTTP.
(Branch #3 A3: Tavily WON ze stosu; kolejność Parallel -> Brave -> Exa-HTTP.)

Cechy:
1. Stdlib-only: zero zewnętrznych zależności (urllib, concurrent.futures).
2. Dual-Engine Ensemble: równoległe odpytywanie 2 silników naraz w ~500ms.
3. Consensus Detection: wykrywanie URL-i potwierdzonych przez 2+ niezależne źródła
   (zgodnie z wymogiem SOP scout-agenta i oceną Admiralty).
4. Automatyczny Fallback: w razie błędu 429/limitu jednego silnika, drugi
   transparentnie dostarcza wyniki bez przerywania pracy agenta.
5. Czysta normalizacja linków: usuwanie parametrów śledzących UTM, ref itp.

Użycie CLI:
    python3 core/lib/search_router.py "zapytanie OSINT" --count 5
    python3 core/lib/search_router.py "zapytanie" --mode waterfall
    python3 core/lib/search_router.py "zapytanie" --json
"""

import argparse
import concurrent.futures
from dataclasses import asdict, dataclass
import json
import os
import sys
import time
from typing import Any
import urllib.parse
import urllib.request

# ─── Modele danych ───────────────────────────────────────────────────────────

@dataclass
class SearchResultItem:
    title: str
    url: str
    canonical_url: str
    snippet: str
    providers: list[str]
    consensus: bool
    score: float

# ─── Konfiguracja i ładowanie zmiennych środowiskowych ───────────────────────

def _load_env_fallback() -> dict[str, str]:
    """Wczytuje zmienne z .env, jeśli nie ma ich w os.environ."""
    env: dict[str, str] = {}
    candidates = [
        os.path.join(os.getcwd(), ".env"),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env")),
    ]
    for env_path in candidates:
        if os.path.isfile(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        stripped = line.strip()
                        if not stripped or stripped.startswith("#") or "=" not in stripped:
                            continue
                        k, v = stripped.split("=", 1)
                        env[k.strip()] = v.strip().strip("\"'")
                break
            except OSError:
                continue
    return env

_FILE_ENV = _load_env_fallback()

def get_api_key(name: str) -> str | None:
    """Zwraca klucz z os.environ lub z pliku .env."""
    key = os.environ.get(name) or _FILE_ENV.get(name)
    if key and not any(key.startswith(pfx) for pfx in ("tvly-twoj", "BSA_twoj", "prl_twoj", "twoj_")):
        return key
    return None

# ─── Normalizacja URL ────────────────────────────────────────────────────────

_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "msclkid", "ref", "source", "mc_cid", "mc_eid",
}

def canonicalize_url(url: str) -> str:
    """Oczyszcza URL ze śmieci śledzących i normalizuje schemat/ścieżkę."""
    try:
        parsed = urllib.parse.urlparse(url.strip())
        netloc = parsed.netloc.lower().removeprefix("www.")
        
        # Filtrujemy query parametry
        if parsed.query:
            query_tuples = urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
            filtered = [(k, v) for k, v in query_tuples if k.lower() not in _TRACKING_PARAMS]
            clean_query = urllib.parse.urlencode(filtered)
        else:
            clean_query = ""
            
        path = parsed.path.rstrip("/")
        return urllib.parse.urlunparse((
            parsed.scheme.lower() or "https",
            netloc,
            path,
            "",
            clean_query,
            "",
        ))
    except (ValueError, AttributeError):
        return url.strip().rstrip("/")

# ─── Adaptery dostawców wyszukiwania ─────────────────────────────────────────
def search_parallel(query: str, count: int = 5, timeout: float = 8.0) -> list[dict[str, Any]]:
    """Wywołanie Parallel Search API (5 000 req/mc, zoptymalizowane pod agentów AI)."""
    api_key = get_api_key("PARALLEL_API_KEY")
    if not api_key:
        raise ValueError("Brak PARALLEL_API_KEY w środowisku / .env")

    req = urllib.request.Request(
        "https://api.parallel.ai/v1/search",
        data=json.dumps({
            "objective": query,
            "search_queries": [query],
            "mode": "fast",
        }).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "User-Agent": "OmegaSearchRouter/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))

    results: list[dict[str, Any]] = []
    raw_results = data.get("results")
    if isinstance(raw_results, list):
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url", ""))
            if not url:
                continue
            excerpts = item.get("excerpts", [])
            snippet = "\n".join(excerpts) if isinstance(excerpts, list) else str(excerpts or "")
            results.append({
                "title": str(item.get("title", "")),
                "url": url,
                "snippet": snippet,
                "provider": "parallel",
                "raw_score": 0.0,
            })
    return results[:count]


def search_tavily(*args: object, **kwargs: object) -> object:
    """USUNIETE w Branch #3 (A3): Tavily WON ze stosu; Parallel -> Brave -> Exa-HTTP."""
    raise RuntimeError("Provider tavily usuniety (Branch #3 A3: stos Parallel -> Brave -> Exa-HTTP).")


def search_brave(query: str, count: int = 5, timeout: float = 8.0) -> list[dict[str, Any]]:
    """Wywołanie Brave Web Search API (niezależny indeks webowy)."""
    api_key = get_api_key("BRAVE_API_KEY")
    if not api_key:
        raise ValueError("Brak BRAVE_API_KEY w środowisku / .env")

    params = urllib.parse.urlencode({"q": query, "count": max(1, min(count, 20))})
    url = f"https://api.search.brave.com/res/v1/web/search?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "X-Subscription-Token": api_key,
            "Accept": "application/json",
            "User-Agent": "OmegaSearchRouter/1.0",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))

    results: list[dict[str, Any]] = []
    web_obj = data.get("web")
    if isinstance(web_obj, dict):
        web_results = web_obj.get("results")
        if isinstance(web_results, list):
            for item in web_results:
                if not isinstance(item, dict):
                    continue
                url = str(item.get("url", ""))
                if not url:
                    continue
                results.append({
                    "title": str(item.get("title", "")),
                    "url": url,
                    "snippet": str(item.get("description", "")),
                    "provider": "brave",
                    "raw_score": 0.0,
                })
    return results

def search_exa(query: str, count: int = 5, timeout: float = 8.0) -> list[dict[str, Any]]:
    """Wywołanie Exa AI Search API (semantyczne wyszukiwanie zapasowe)."""
    api_key = get_api_key("EXA_API_KEY")
    if not api_key:
        raise ValueError("Brak EXA_API_KEY w środowisku / .env")

    req = urllib.request.Request(
        "https://api.exa.ai/search",
        data=json.dumps({
            "query": query,
            "numResults": max(1, count),
            "type": "auto",
        }).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "User-Agent": "OmegaSearchRouter/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))

    results: list[dict[str, Any]] = []
    raw_results = data.get("results")
    if isinstance(raw_results, list):
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url", ""))
            if not url:
                continue
            snippet = str(item.get("text") or item.get("highlight") or "")
            results.append({
                "title": str(item.get("title", "")),
                "url": url,
                "snippet": snippet,
                "provider": "exa",
                "raw_score": float(item.get("score") or 0.0),
            })
    return results

# ─── Reciprocal Rank Fusion & Fuzja wyników ──────────────────────────────────

def fuse_results(
    engine_results: dict[str, list[dict[str, Any]]],
    limit: int = 10,
    rrf_k: int = 60,
) -> list[SearchResultItem]:
    """Łączy wyniki z wielu silników za pomocą Reciprocal Rank Fusion (RRF)."""
    fused_map: dict[str, SearchResultItem] = {}

    for provider, items in engine_results.items():
        for rank, item in enumerate(items, start=1):
            raw_url = str(item.get("url", ""))
            can_url = canonicalize_url(raw_url)
            rrf_score = 1.0 / (rrf_k + rank)

            if can_url not in fused_map:
                fused_map[can_url] = SearchResultItem(
                    title=str(item.get("title", "")),
                    url=raw_url,
                    canonical_url=can_url,
                    snippet=str(item.get("snippet", "")),
                    providers=[provider],
                    consensus=False,
                    score=rrf_score,
                )
            else:
                entry = fused_map[can_url]
                if provider not in entry.providers:
                    entry.providers.append(provider)
                entry.score += rrf_score
                new_snippet = str(item.get("snippet", ""))
                if len(new_snippet) > len(entry.snippet):
                    entry.snippet = new_snippet
                if not entry.title and item.get("title"):
                    entry.title = str(item["title"])

    # Oznaczamy consensus jeśli potwierdzone przez >1 niezależny silnik
    for entry in fused_map.values():
        entry.consensus = len(entry.providers) > 1

    # Sortowanie: Consensus na samej górze, potem wg sumarycznego RRF score
    sorted_items = sorted(
        fused_map.values(),
        key=lambda x: (1 if x.consensus else 0, x.score),
        reverse=True,
    )
    return sorted_items[:limit]

# ─── Cohere Cross-Encoder Reranker ──────────────────────────────────────────

def rerank_cohere(
    query: str,
    items: list[SearchResultItem],
    top_n: int = 5,
    timeout: float = 6.0,
) -> tuple[list[SearchResultItem], str | None]:
    """Przelicza trafność semantyczną wyników modelem Cross-Encoder Cohere rerank-v3.5."""
    api_key = get_api_key("COHERE_API_KEY")
    if not api_key or not items:
        return items[:top_n], None

    try:
        docs = [f"{it.title}\n{it.snippet}".strip() for it in items]
        req = urllib.request.Request(
            "https://api.cohere.com/v2/rerank",
            data=json.dumps({
                "model": "rerank-v3.5",
                "query": query,
                "documents": docs,
                "top_n": min(top_n, len(items)),
            }).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "OmegaSearchRouter/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))

        reranked: list[SearchResultItem] = []
        raw_results = data.get("results")
        if isinstance(raw_results, list):
            for r in raw_results:
                if not isinstance(r, dict):
                    continue
                idx = int(r.get("index", 0))
                rel_score = float(r.get("relevance_score", 0.0))
                if 0 <= idx < len(items):
                    item = items[idx]
                    item.score = round(rel_score, 4)
                    reranked.append(item)
            return reranked, None
    except Exception as e:  # noqa: BLE001
        return items[:top_n], str(e)

    return items[:top_n], None


def _local_tokens(text: str) -> list[str]:
    import re as _re
    return _re.findall(r"[a-z0-9]+", (text or "").lower())


def rerank_local(
    query: str,
    items: list[SearchResultItem],
    top_n: int = 5,
) -> tuple[list[SearchResultItem], None]:
    """Lokalny fallback rerank (Branch #3 A4, stdlib, deterministyczny).

    Cosine TF na tokenach alfanumerycznych query vs (tytuł + snippet).
    Używany gdy Cohere niedostępny (brak klucza) lub zgłosi błąd —
    zamiast graceful-skip w nicość. Zwraca (posortowane, None).
    """
    if not items:
        return [], None
    q_toks = _local_tokens(query)
    q_set = set(q_toks)
    q_norm = len(q_toks) ** 0.5 if q_toks else 0.0
    scored: list[tuple[float, int]] = []
    for idx, it in enumerate(items):
        d_toks = _local_tokens(f"{it.title} {it.snippet}")
        if not d_toks or not q_set:
            scored.append((0.0, idx))
            continue
        d_counts: dict[str, int] = {}
        for t in d_toks:
            d_counts[t] = d_counts.get(t, 0) + 1
        dot = sum(d_counts.get(t, 0) for t in q_set)
        d_norm = sum(v * v for v in d_counts.values()) ** 0.5
        cos = dot / (q_norm * d_norm) if (q_norm and d_norm) else 0.0
        scored.append((round(cos, 4), idx))
    scored.sort(key=lambda p: (-p[0], p[1]))
    out: list[SearchResultItem] = []
    for score, idx in scored[: max(1, top_n)]:
        items[idx].score = score
        out.append(items[idx])
    return out, None

# ─── Główne strategie wyszukiwania ──────────────────────────────────────────

def ensemble_search(query: str, count: int = 5, timeout: float = 8.0, rerank: bool = True) -> dict[str, Any]:
    """Wyszukiwanie równoległe w Parallel + Brave z fuzją consensus, failoverem Exa-HTTP i rerankiem 2-warstwowym."""
    start_time = time.time()
    providers_attempted: list[str] = []
    providers_succeeded: list[str] = []
    engine_results: dict[str, list[dict[str, Any]]] = {}
    errors: dict[str, str] = {}

    # 1. Para główna (Branch #3 A3): zawsze Parallel + Brave równolegle.
    # Brak klucza = dany silnik zgłasza błąd i drugi transparentnie dostarcza.
    targets = [("parallel", search_parallel), ("brave", search_brave)]
    fallback_fn = ("exa", search_exa)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_map = {
            executor.submit(fn, query, max(count, 5), timeout): name
            for name, fn in targets
        }
        for future in concurrent.futures.as_completed(future_map):
            name = future_map[future]
            providers_attempted.append(name)
            try:
                res = future.result()
                engine_results[name] = res
                providers_succeeded.append(name)
            except Exception as e:  # noqa: BLE001
                errors[name] = str(e)

    # 2. Failover: jeśli para główna dała <2 sukcesy, dogrywka Exa-HTTP (2nd fallback, A3)
    if len(providers_succeeded) < 2 and fallback_fn[0] not in providers_attempted and get_api_key(f"{fallback_fn[0].upper()}_API_KEY"):
        providers_attempted.append(fallback_fn[0])
        try:
            fb_res = fallback_fn[1](query, max(count, 5), timeout)
            if fb_res:
                engine_results[fallback_fn[0]] = fb_res
                providers_succeeded.append(fallback_fn[0])
        except Exception as e:  # noqa: BLE001
            errors[fallback_fn[0]] = str(e)

    # 3. Ostateczny głęboki failover do Exa, jeśli brak jakichkolwiek wyników
    if not engine_results and "exa" not in providers_attempted and get_api_key("EXA_API_KEY"):
        providers_attempted.append("exa")
        try:
            exa_res = search_exa(query, count, timeout)
            engine_results["exa"] = exa_res
            providers_succeeded.append("exa")
        except Exception as e:  # noqa: BLE001
            errors["exa"] = str(e)
    # 3. Fuzja i deduplikacja (szersza pula pod 2-warstwowy rerank)
    candidate_limit = min(15, count * 2) if rerank else count
    fused_items = fuse_results(engine_results, limit=candidate_limit)

    # 4. Rerank 2-warstwowy (Branch #3 A4): Cohere primary + lokalny fallback.
    # Brak klucza Cohere lub błąd API NIE oznacza skip w nicość — zawsze
    # schodzimy na warstwę lokalną (stdlib, deterministyczna).
    rerank_applied = False
    rerank_layer: str | None = None
    if rerank and fused_items:
        if get_api_key("COHERE_API_KEY"):
            fused_items, rerank_err = rerank_cohere(query, fused_items, top_n=count, timeout=timeout)
            if rerank_err:
                errors["cohere_rerank"] = rerank_err
                fused_items, _ = rerank_local(query, fused_items, top_n=count)
                rerank_applied = True
                rerank_layer = "local"
            else:
                rerank_applied = True
                rerank_layer = "cohere"
        else:
            fused_items, _ = rerank_local(query, fused_items, top_n=count)
            rerank_applied = True
            rerank_layer = "local"
    else:
        fused_items = fused_items[:count]

    elapsed = round(time.time() - start_time, 3)

    return {
        "query": query,
        "mode": "ensemble",
        "reranked": rerank_applied,
        "rerank_layer": rerank_layer,
        "elapsed_seconds": elapsed,
        "providers_attempted": providers_attempted,
        "providers_succeeded": providers_succeeded,
        "consensus_count": sum(1 for x in fused_items if x.consensus),
        "total_results": len(fused_items),
        "errors": errors,
        "results": [asdict(x) for x in fused_items],
    }
def waterfall_search(query: str, count: int = 5, timeout: float = 8.0) -> dict[str, Any]:
    """Wyszukiwanie sekwencyjne Parallel -> Brave -> Exa-HTTP (oszczędza zapytania; A3)."""
    start_time = time.time()
    providers_attempted: list[str] = []
    errors: dict[str, str] = {}

    sequence = [
        ("parallel", search_parallel),
        ("brave", search_brave),
        ("exa", search_exa),
    ]

    for name, fn in sequence:
        providers_attempted.append(name)
        try:
            res = fn(query, count, timeout)
            if res:
                fused_items = fuse_results({name: res}, limit=count)
                return {
                    "query": query,
                    "mode": "waterfall",
                    "elapsed_seconds": round(time.time() - start_time, 3),
                    "providers_attempted": providers_attempted,
                    "providers_succeeded": [name],
                    "consensus_count": 0,
                    "total_results": len(fused_items),
                    "errors": errors,
                    "results": [asdict(x) for x in fused_items],
                }
        except Exception as e:  # noqa: BLE001
            errors[name] = str(e)

    return {
        "query": query,
        "mode": "waterfall",
        "elapsed_seconds": round(time.time() - start_time, 3),
        "providers_attempted": providers_attempted,
        "providers_succeeded": [],
        "consensus_count": 0,
        "total_results": 0,
        "errors": errors,
        "results": [],
    }

# ─── Formatowanie CLI i Main ────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Omega-v3 Federated Search Router")
    _ = parser.add_argument("query", type=str, help="Zapytanie do wyszukiwarki")
    _ = parser.add_argument("-n", "--count", type=int, default=5, help="Liczba wyników (domyślnie 5)")
    _ = parser.add_argument("-m", "--mode", choices=["ensemble", "waterfall"], default="ensemble",
                            help="Tryb wyszukiwania: ensemble (redundancja) lub waterfall (sekwencyjny)")
    _ = parser.add_argument("--json", action="store_true", help="Zwróć wynik jako surowy JSON")
    _ = parser.add_argument("--no-rerank", action="store_true", help="Wyłącz reranking semantyczny Cohere")
    _ = parser.add_argument("-t", "--timeout", type=float, default=8.0, help="Timeout na zapytanie w sekundach")
    args = parser.parse_args()

    if args.mode == "ensemble":
        result = ensemble_search(args.query, count=args.count, timeout=args.timeout, rerank=not args.no_rerank)
    else:
        result = waterfall_search(args.query, count=args.count, timeout=args.timeout)

    if args.json or not sys.stdout.isatty():
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    mode_str = "DUAL ENSEMBLE (Redundancja)" if result["mode"] == "ensemble" else "WATERFALL (Sekwencyjny)"
    _layer = result.get("rerank_layer") or ("cohere" if result.get("reranked") else "")
    rerank_str = f" + Rerank:{_layer}" if result.get("reranked") else ""
    print(f"\n🔍 Szukano: '{result['query']}' [{mode_str}{rerank_str}] w {result['elapsed_seconds']}s")
    print(f"📡 Silniki: udane: {result['providers_succeeded']} (próbowane: {result['providers_attempted']})")
    consensus_cnt = int(result.get("consensus_count", 0))
    if consensus_cnt > 0:
        print(f"⭐ Consensus (2+ źródła): {consensus_cnt} wyników\n")
    else:
        print(f"Wyniki: {result['total_results']}\n")

    results_list = result.get("results", [])
    for idx, r in enumerate(results_list, start=1):
        provs = r.get("providers", [])
        prov_tag = "+".join(provs)
        cons_tag = " [CONSENSUS ⭐]" if r.get("consensus") else ""
        score = float(r.get("score", 0.0))
        print(f"{idx}. {r.get('title')}{cons_tag}")
        print(f"   URL: {r.get('url')}")
        print(f"   Źródło: {prov_tag} | Score: {score:.4f}")
        snippet = str(r.get("snippet", ""))
        if snippet:
            snippet_clean = snippet.replace("\n", " ").strip()
            if len(snippet_clean) > 200:
                snippet_clean = snippet_clean[:197] + "..."
            print(f"   Fragment: {snippet_clean}")
        print()

if __name__ == "__main__":
    main()
