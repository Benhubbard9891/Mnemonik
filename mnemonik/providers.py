"""Offline deterministic test embedding; not a semantic embedding model."""
import hashlib
import math
class AsyncEmbedder:
    async def embed(self, text: str) -> list[float]:
        raise NotImplementedError

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

class AsyncHashingEmbedder(AsyncEmbedder):
    def __init__(self, dim: int = 64):
        self.dim = dim

    async def embed(self, text: str) -> list[float]:
        clean = text.lower().strip()
        vector: list[float] = []
        for index in range(self.dim):
            digest = hashlib.sha256(f"{clean}|dimension:{index}".encode("utf-8")).digest()
            raw = int.from_bytes(digest[:8], "big")
            normalized = raw / ((1 << 64) - 1)
            vector.append((normalized * 2.0) - 1.0)
        norm = math.sqrt(sum(value * value for value in vector))
        if norm <= 1e-12: return [0.0] * self.dim
        return [value / norm for value in vector]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [await self.embed(text) for text in texts]
