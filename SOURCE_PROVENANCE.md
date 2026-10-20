# Source provenance

Refactored from the engine embedded in `mnemonik_v31_colab_verify.ipynb` in Benhubbard9891/Mnemonik.

Original extracted engine SHA-256: `5480cff980337875281fb0d2b73201f97493f69ef25cd0600e05db1d6d641751`.

Preserved: fact/result models, deterministic embedding, dense cosine and FTS5 BM25 ranking primitives. Replaced: persistence lifecycle, mutation/reconciliation boundary, index transactions, scope filters, and audit implementation. Legacy maintenance sketch retained only for compatibility, not for use against the new database. No cloud adapter is bundled in this offline release candidate.
