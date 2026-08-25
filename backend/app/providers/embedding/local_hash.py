"""Offline feature-hashing embedding, explicitly labelled for demo use."""

import hashlib
import math
import re


class LocalHashEmbeddingProvider:
    name = "local_feature_hash"
    dimensions = 384

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vector = [0.0] * self.dimensions
            for token in re.findall(r"[\w\u4e00-\u9fff]+", text.lower()):
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                index = int.from_bytes(digest[:4], "big") % self.dimensions
                vector[index] += 1.0 if digest[4] % 2 == 0 else -1.0
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            vectors.append([value / norm for value in vector])
        return vectors
