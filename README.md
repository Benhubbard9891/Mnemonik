# Mnemonik Evoke 1.0.0rc1

Canonical SQLite/FTS5 memory substrate with structured facts, ranking, and audit.

## Install (wheel)

```bash
pip install dist/mnemonik_evoke-1.0.0rc1-py3-none-any.whl
```

## Quick start

```python
from mnemonik import MemoryStore

store = MemoryStore("memory.db")
store.add_fact("User prefers dark theme", tags=["preference"])
print(store.search("theme"))
```

See `VERIFICATION.md` and `SOURCE_PROVENANCE.md` for release integrity notes.
