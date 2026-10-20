# Verification — 1.0.0rc1

Executed October 20, 2026 UTC (October 19 in America/New_York).

Environment: Python 3.12.14, SQLite 3.53.1 with FTS5, aiosqlite 0.21.0, typing_extensions 4.16.0, setuptools 84.0.0.

## Observed results

- `python -m unittest discover -s tests -v`: **46 passed** — 26 existing legacy mock tests and 20 new release-gate integration tests.
- Synthetic Toro example: **passed**, including exact logical fact, vector, FTS, edge and receipt comparison after close/reopen.
- Installed-package CLI outside the source directory: **passed**, returning the corrected active diagnosis.
- CLI history and audit: **passed**, both versions preserved and two valid receipts.
- Wheel build and package installation: **passed**.

Logs: `verification/tests.txt`, `verification/toro-demo.txt`, `verification/cli-history.json`, `verification/cli-audit.json`.

## Release gates exercised

Scope and subject filtering; stale-target rejection; linked supersession; audited duplicate NOOP; simultaneous writers on one connection and separate connections; rollback after index deletion/embedding failure; rollback after receipt failure; task cancellation; malformed embedding batches; dimension mismatch; clock regression; invalid scope; finite nonnegative fusion weights; FTS operator-token quoting; restart equality; fact/index/receipt tampering; external-anchor mismatch; restoration of an older SQLite backup; abrupt child-process exit before commit followed by recovery.

## Limits

Tests are bounded examples, not a proof for arbitrary concurrency, hardware failures or hostile operating systems. The process-exit test calls os._exit during an uncommitted write; it does not emulate electrical power loss or storage-controller failure. Hash anchors must be independently trusted. No cloud model, semantic retrieval benchmark, authenticated identity, digital signature, encryption, security-risk experiment or production-scale load test was performed.

The original notebook's historical 11-test output is not counted in the 46 tests. Its embedded implementation was replaced with imports of the canonical package. Original source remains in git history; SOURCE_PROVENANCE.md records extraction identity.
