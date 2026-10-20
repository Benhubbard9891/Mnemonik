# 1.0.0rc1

- Extract SQLite/FTS5 and ranking primitives into a canonical package.
- Introduce disk-backed schema version 1 and explicit structured fact API.
- Replace mutable UPDATE reconciliation with linked supersession.
- Require scope and constrain corrections by subject/predicate/scope.
- Add stale-head checks, atomic index/receipt writes, and rollback on cancellation.
- Add hash-linked audit receipts, external-head verification, CLI and synthetic Toro demo.
- Retain the original maintenance sketch as a legacy import.
- Replace the self-contained notebook with imports from the installed package.

Breaking differences from the notebook: no free-text observe(), no automatic provider selection, no implicit cross-subject reconciliation, no read-triggered reinforcement, and no claim of full bitemporal storage or authenticated authorship.
