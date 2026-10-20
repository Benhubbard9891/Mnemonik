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

See `VERIFICATION.md`, `SOURCE_PROVENANCE.md`, and `SECURITY.md` for integrity notes and limits.

MIT license. No GitHub release or package-registry publication is implied by this checkout.
