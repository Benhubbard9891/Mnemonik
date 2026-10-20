from dataclasses import dataclass
from typing import Optional, Any

@dataclass
class Fact:
    id: str
    subject: str
    predicate: str
    value: str
    scope: str
    actor: str
    evidence: str
    sequence: int
    timestamp: str
    supersedes: Optional[str] = None
    active: bool = True

@dataclass
class RecallResult:
    fact: Fact
    score: float
    rank: int

@dataclass
class Clock:
    sequence: int
    head: str
