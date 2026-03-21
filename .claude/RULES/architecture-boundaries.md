# Architecture Boundaries

These are non-negotiable invariants derived from ADR-001 and ARCHITECTURE.md (P1–P6). Violations produce wrong behaviour regardless of whether tests pass.

- `compiler/` must never import from `engine/` or `algos/`. The compiler is strictly structural — it parses, validates, and instantiates. AlgoStack construction belongs to `Runner.__init__()`.
- No allocation logic outside an Algo's `__call__`. Selection and weighting decisions must not live in `runner.py`, node classes, or anywhere else.
- The Upward Pass must fully complete before the Downward Pass begins — on every day, without exception. No interleaving.
- A node must never access its parent, siblings, or grandchildren. The only interface is `target` (the node itself).
