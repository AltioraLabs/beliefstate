import math
import struct
from typing import List


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if not v1 or not v2:
        return 0.0
    if len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    mag1 = math.sqrt(sum(a * a for a in v1))
    mag2 = math.sqrt(sum(b * b for b in v2))
    if mag1 == 0.0 or mag2 == 0.0:
        return 0.0
    return float(dot / (mag1 * mag2))


def pack_embedding(embedding: List[float]) -> bytes:
    """Pack float32 array as binary bytes for storage."""
    if not embedding:
        return b""
    return struct.pack(f"{len(embedding)}f", *embedding)


def unpack_embedding(data: bytes) -> List[float]:
    """Unpack binary bytes back to float32 list."""
    if not data:
        return []
    n = len(data) // 4
    return list(struct.unpack(f"{n}f", data))
