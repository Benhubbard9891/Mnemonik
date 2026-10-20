from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import time

@dataclass(frozen=True)
class Fact:
    id: str
    subject: str
    predicate: str
    object: str
    scope: Optional[str] = None
    valid_from: Optional[float] = None
    valid_to: Optional[float] = None
    supersedes: Optional[str] = None
    created_at: float = 0.0
    strength: float = 1.0
    last_accessed: float = 0.0
    provenance: str = ""

@dataclass(frozen=True)
class RecallResult:
    fact: Fact
    dense_score: float
    sparse_score: float
    fused_score: float
    graph_score: float = 0.0

class Clock:
    def __init__(self, t0: float = 0.0):
        self._now = float(t0)

    def now(self) -> float:
        return self._now

    def advance(self, delta: float) -> None:
        if delta < 0:
            raise ValueError("Time cannot flow backwards.")
        self._now += float(delta)

class SystemClock:
    def now(self):
        return time.time()
