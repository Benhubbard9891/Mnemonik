# Security and evidence boundaries

This is a local single-user reference component. Protect its directory using operating-system permissions. Actor strings and evidence are untrusted caller assertions. Scope filtering is not authentication, authorization, tenant isolation, or encryption. Do not expose the CLI or raw SQLite connection as a remote service.

Receipts are SHA-256 hash links, not digital signatures. The latest logical state hash covers facts, vectors, FTS source rows and edge rows. SQLite integrity checks are supplementary; no claim is made that all internal FTS shadow-table corruption is detected. Save receipt heads in an independently protected location if rollback detection matters. Backup/restore must preserve that external trust anchor. No key management or external timestamp authority is supplied.

The engine checks existing receipt/state consistency before writes and recall and on open. Direct SQL writers bypass API guarantees; coordinated state and receipt forgery is outside this trust model. The `legacy` module is not part of the audited write boundary.

Input facts are data. This package neither evaluates their truth nor executes their contents. A calling agent must enforce its own authority and evidence policies. No statistical safety or Layer 2 evaluation results are asserted.

Resource limits, large-corpus tuning, adversarial multi-user access and physical power-loss qualification remain future release work. Snapshot hashing and full index rebuilding are O(database size); use small bounded local datasets for this candidate.
