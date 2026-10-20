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

Building requires setuptools 84.0.0; install `build-requirements.txt` if it is not available. A prebuilt wheel is referenced in `dist/SHA256SUMS`. The demo refuses to overwrite an existing database; omit `--db` for a temporary demo. All demo and engine operations then run without network access or API keys.

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
        scope='work-order-17', actor='technician-A', evidence='Follow-up find',
        expected_id=original.id,
    )
    results = await memory.recall('diagnosis', scope='work-order-17')
    history = await memory.history('asset-42', 'diagnosis', scope='work-order-17')
    audit = await memory.verify()
```

## Repository layout

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
- `dist/SHA256SUMS`: checksums for the release tree and wheel

See `VERIFICATION.md`, `SOURCE_PROVENANCE.md`, and `SECURITY.md` for integrity notes and limits.

MIT license. No GitHub release or package-registry publication is implied by this checkout.
