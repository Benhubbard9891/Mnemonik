# Verification — 1.0.0rc1

Executed October 20, 2026 UTC (October 19 in America/New_York).

Environment: Python 3.12.14, SQLite 3.53.1 with FTS5, aiosqlite 0.21.0, typing_extensions 4.16.0, setuptools 84.0.0.

## Observed results

- `python -m unittest discover -s tests -v`: **46 passed** — 26 existing legacy mock tests and 20 new release-gate integration tests.
- Synthetic Toro example: **passed**, including exact logical fact, vector, FTS, edge and receipt comparison after close/reopen.
- Installed-package CLI outside the source directory: **passed**, returning the corrected active diagnosis.
- CLI history and audit: **passed**, both versions preserved and two valid receipts.
- Wheel build and package installation: **passed**.

Logs: `verification/tests.txt`, `verification/toro-demo.txt`

See full release tree for remaining verification artifacts and limits.
