# Reviewer Guide — dSearch

## Review State

* **Current revision:** `main` (`9f9f1be`)
* **Test suite:** 78 tests passed in CI (`python3 -m pytest tests/`, ~0.3s runtime)
* **Static analysis:** `ruff check .` (0 errors), `mypy` (0 issues across 14 source files)
* **License:** MIT · Single-author repository

---

## What This Repository Demonstrates

* **Empirical search-consensus falsification:** Directly tested the industry assumption that search-engine agreement equals result accuracy, evaluating multi-engine consensus across 60 labelled document queries.
* **Rigorous statistical measurement:** Measured strict precision at **0.1456** (Wilson 95% CI [0.108, 0.194]): out of 261 consensus URLs, only 38 matched the ground-truth document.
* **Halt on negative data:** Stopped backend runtime and MCP development based on measured data rather than shipping an unverified wrapper; preserved the antecedent router in `archive/` with full audit notes.
* **Architectural purity & dependency boundaries:** AST-level test (`tests/test_dependency_policy.py`) enforcing that `core/` contains pure algorithmic logic with zero network I/O (`httpx`, `requests`, `urllib.request` strictly forbidden).

---

## What This Repository Does NOT Demonstrate

* **No active production SaaS or MCP service:** The product buildout was intentionally halted and archived when empirical data showed multi-engine consensus produced unacceptable precision (0.1456).
* **No model fine-tuning:** Evaluated multi-engine retrieval consensus, not LLM weights.
* **No multi-contributor team development:** Single-author repository with self-administered reviews and CI automation.

---

## Fast Review Path (10 Minutes)

1. **Empirical Study & Methodology:** [`README.md`](README.md) — Falsification findings, Wilson CI calculations, and off-target failure analysis.
2. **Consensus Engine:** [`core/consensus.py`](core/consensus.py) — Agreement computation, thresholding, and consensus rate logic.
3. **Deterministic Canonicalization:** [`core/canonical.py`](core/canonical.py) — Strict URL normalization (stripping tracking params, fragments, default ports).
4. **Dependency Policy Gate:** [`tests/test_dependency_policy.py`](tests/test_dependency_policy.py) — AST inspection ensuring pure algorithmic core boundaries.
5. **Archived Antecedent Implementation:** [`archive/search_router_v1.py`](archive/search_router_v1.py) & [`archive/README.md`](archive/README.md) — The 4-engine fallback router and budget manager that was archived upon negative study findings.

---

## Reproduce the Review State

```bash
git checkout main

# 1. Run unit test suite (78 tests)
python3 -m pytest tests/

# 2. Run static analysis & type checks
ruff check .
python3 -m mypy core providers scripts
```

Expected output:
* `78 passed in ~0.3s`
* `ruff check .` -> `All checks passed!`
* `mypy` -> `Success: no issues found in 14 source files`

---

## One Control Worth Falsifying

**Invariant:** `core/` must remain pure algorithmic logic with zero network I/O; importing HTTP clients (`httpx`, `requests`, `urllib.request`) is strictly forbidden.
* Verification: [`tests/test_dependency_policy.py`](tests/test_dependency_policy.py) enforces this via AST inspection of all files in `core/`.
* You can test this control by adding `import httpx` to `core/canonical.py` and running the test:
  ```bash
  python3 -c "
  with open('core/canonical.py', 'r') as f: content = f.read()
  with open('core/canonical.py', 'w') as f: f.write('import httpx\n' + content)
  "
  python3 -m pytest tests/test_dependency_policy.py
  git checkout core/canonical.py
  ```
  Expected output:
  * `FAILED tests/test_dependency_policy.py::test_repository_satisfies_dependency_policy`
  * `HTTP client import 'httpx' is disallowed` (exit code `1`)

---

## Authorship & AI Assistance

Single-author repository. Tomasz Gonczar owns all experiment designs, ground-truth labelling, architectural decisions, invariants, and project shutdown decisions. Coding agents (Claude Code / Codex / Antigravity CLI) were used as execution pair-programmers. PR reviews, CI pipelines, and gates are self-administered.

---

## Known Limits

1. **Benchmark dataset scope:** 60 labelled document queries; sufficient for directional falsification (Wilson CI [0.108, 0.194]), but not a universal web retrieval benchmark.
2. **Archived runtime status:** Code in `archive/` is preserved for historical audit; live engine was halted.
