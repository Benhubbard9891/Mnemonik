# MnēmonikEvoke

**Local fact memory with inspectable corrections and hash-linked receipts.**
Benjamin L. Hubbard III · `1.0.0rc1` · release candidate

Store structured facts, replace an incorrect diagnosis without erasing it, inspect the history, and recover the same logical record after restart. This release extracts the v3.1 notebook's SQLite/FTS5 and ranking primitives into one importable package. It is a local memory component, not an authorization kernel or a complete agent platform.

## Quick start

Python 3.10+ and a SQLite build with FTS5 are required. Tested on Python 3.12 in the included verification report.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install --no-deps --no-build-isolation .
python examples/equipment_pilot.py --db toro-demo.db
mnemonik --db toro-demo.db recall 'Toro drive failure' --scope demo:fleet-01
mnemonik --db toro-demo.db history --subject 'Toro TimeCutter Zero-Turn' --predicate drive_diagnosis --scope demo:fleet-01
mnemonik --db toro-demo.db audit
python -m unittest discover -s tests -v
```

Building requires setuptools 84.0.0; install `build-requirements.txt` if it is not available. A prebuilt wheel is included in the delivery bundle. The demo refuses to overwrite an existing database; omit `--db` for a temporary demo. Dependencies need an initial install or a locally supplied wheelhouse; all demo and engine operations then run without network access or API keys.

## Toro demonstration

[examples/equipment_pilot.py](examples/equipment_pilot.py) records a **synthetic** hydraulic-seal diagnosis, supersedes it with the supplied Wescon cable correction, and displays both versions. It closes the connection, reopens the on-disk database, compares the complete logical facts/vector/FTS/edge/receipt snapshots, verifies the retained receipt head, and checks active retrieval again. It does not establish that this diagnosis or part is correct for a particular real mower.

## API

```python
from mnemonik import MemoryEngine

async with MemoryEngine('memory.db') as memory:
    original = await memory.put(
        'asset-42', 'diagnosis', 'Initial diagnosis',
        scope='work-order-17', actor='technician-A', evidence='Inspection notes',
        expected_id='',  # require that no current value exists
    )
    corrected = await memory.put(
        'asset-42', 'diagnosis', 'Corrected diagnosis',
        scope='work-order-17', actor='technician-A', evidence='Follow-up findings',
        expected_id=original.id,
    )
    receipt = await memory.verify()
```

There is exactly one current fact per `(scope, subject, predicate)`. A changed value creates a new ID linked by `supersedes`; the prior version retains its text and provenance and receives `valid_to`. Equal values produce an audited NOOP. `expected_id` is an optimistic concurrency guard; `None` allows a serialized upsert, while `''` requires an empty slot. Subject and scope matching are exact after trimming, case-sensitive, with no implicit entity merging. Use asset IDs/scopes to distinguish physically separate machines of the same model.

`recall` requires an explicit scope and optionally filters by subject. It returns active facts by default; `include_history=True` includes superseded versions. It does not reinforce or mutate facts. Dense cosine, FTS5 BM25 and rank-based graph fusion are retained, but the default deterministic hashing embedder is a **test fixture**, not a semantic model. Dense ranking can return irrelevant candidates; this release makes no semantic-accuracy claim. BM25 corpus statistics are database-wide; scope is a record filter, not a tenant security boundary.

## Transactions and integrity

Writes use `BEGIN IMMEDIATE`, foreign keys, a partial unique head index, WAL and `synchronous=FULL`. Fact updates, derived indexes and receipts commit together. Exceptions and task cancellation roll back the transaction. A per-connection async lock prevents interleaved transactions; SQLite serializes independent writers. Index rebuilding and complete state hashing are intentionally simple and scale with database size.

Each receipt binds a sequence number, declared actor, local timestamp, evidence text, operation, fact ID and logical state hash to the previous receipt hash. Verification checks the chain and latest state/index hash. Retain the returned head separately and use `audit --expected-head HASH` to detect a restored older snapshot relative to that retained head.

**Hashes are not signatures.** Actor labels are caller-declared; local time is not a trusted timestamp. A writer who controls the database can rewrite state and recompute the entire chain. Without an independently trusted anchor, coherent rollback or wholesale replacement cannot be detected. Hashes do not prove a diagnosis true or authorize an action. The database is not encrypted, and scopes are not access-control boundaries. See [SECURITY.md](SECURITY.md).

## Scope and compatibility

This candidate supports explicit structured fact ingestion. Natural-language extraction, probabilistic risk inference, cloud providers, reinforcement/decay, distributed consensus and signed identity are outside its core API. Retrieval ranking is advisory, never authorization. The legacy `MnemonikMemoryStore` import remains available for existing callers but must not write to a new engine database: its mutations do not create receipts.

New databases use schema version 1. Unknown or older schemas are rejected; no in-place migration is supplied. This is a version-history store, not a complete bitemporal database. Recovery tests cover application exceptions, cancellation, process exit with an uncommitted write, and normal restart; they are not physical power-loss or filesystem-corruption certification.

## Repository

- `mnemonik/engine.py`: connection lifecycle and transaction boundary
- `mnemonik/operations.py`: scoped writes, linked corrections, retrieval
- `mnemonik/audit.py`: canonical hashing and receipt verification
- `mnemonik/reconciliation.py`: extracted ranking primitives
- `mnemonik/models.py`, `providers.py`: data models and offline test embedder
- `mnemonik/cli.py`: installed inspection command
- `tests/`: legacy tests and release-gate integration tests
- `examples/equipment_pilot.py`: canonical offline workflow
- `mnemonik_v31_colab_verify.ipynb`: imports the package; no embedded engine copy
- `SOURCE_PROVENANCE.md`: extraction origin and intentional behavior changes
- `VERIFICATION.md`: observed results and limits

MIT license. No GitHub release or package-registry publication is implied by this checkout.
