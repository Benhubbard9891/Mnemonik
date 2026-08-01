# Mnemonik

Mnemonik is a lightweight Python memory-store sketch centered on two async
maintenance operations:

- `prune_memory(...)` decays fact retrievability over time and tombstones facts
  that fall below a threshold.
- `reinforce_fact(...)` updates `last_accessed` and boosts a fact's strength
  after successful recall.

## Example implementation

```python
import asyncio

from mnemonik import MnemonikMemoryStore

async def main() -> None:
    store = MnemonikMemoryStore(db=my_async_db, clock=my_clock)

    pruned = await store.prune_memory()
    await store.reinforce_fact("fact-123")


asyncio.run(main())
```

## Behavior

### `prune_memory`

- reads active facts with `valid_to IS NULL`
- computes retrievability with exponential decay
- tombstones facts whose retrievability drops below the configured threshold
- deletes vector and full-text-search rows for pruned facts
- returns the total number of facts pruned in the cycle

### `reinforce_fact`

- raises `RuntimeError` when the database connection is missing
- updates `last_accessed`
- increases `strength` by `reinforcement_value`
- caps `strength` at `1.0`

## Running tests

```bash
python -m unittest discover -s tests -v
```