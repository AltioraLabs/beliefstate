import json
from typing import Any

from typing_extensions import Self

from beliefstate.models import Belief
from beliefstate.store.base import Store
from beliefstate.store.utils import cosine_similarity

try:
    import faiss

    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False


class RedisStore(Store):
    """Redis-based asynchronous storage for beliefs.

    Uses binary float32 embedding storage for precision.

    Vector search is optionally accelerated via FAISS (Facebook AI Similarity Search).
    If FAISS is not available, search_beliefs falls back to an O(n) linear scan
    over all beliefs in the session — adequate for small-to-moderate volumes.
    For high-volume deployments, consider using PostgreSQLStore with pgvector
    for native vector indexing.

    Example:
        >>> store = RedisStore()
        >>> await store.open()
        >>> results = await store.search_beliefs(session_id, embedding, threshold=0.8)
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self._client: Any | None = None
        redis_found = False
        try:
            import redis as redis_module

            redis_found = True
            self._client = redis_module.Redis.from_url(
                redis_url, decode_responses=False
            )
        except ImportError:
            pass
        if not redis_found:
            self._client = None

    async def open(self) -> None:
        """No-op for Redis (client initialized in __init__)."""

    def _get_key(self, session_id: str) -> str:
        return f"beliefstate:session:{session_id}"

    def _get_audit_key(self, session_id: str, subject: str, predicate: str) -> str:
        return f"beliefstate:audit:{session_id}:{subject}::{predicate}"

    async def add_belief(self, session_id: str, belief: Any) -> None:
        if not self._client:
            raise RuntimeError(
                "redis package is not installed. Run `pip install redis`"
            )

        cid = belief.conversation_id or ""
        field = f"{(belief.subject or '').lower()}::{(belief.predicate or '').lower()}::{cid}"
        await self._client.hset(
            self._get_key(session_id), field, belief.model_dump_json()
        )

    async def get_beliefs(
        self, session_id: str, conversation_id: str | None = None
    ) -> list[Any]:
        if not self._client:
            raise RuntimeError(
                "redis package is not installed. Run `pip install redis`"
            )

        data = await self._client.hgetall(self._get_key(session_id))
        beliefs = []
        for value_bytes in data.values():
            if isinstance(value_bytes, bytes):
                value_str = value_bytes.decode("utf-8")
            else:
                value_str = value_bytes
            belief = Belief.model_validate_json(value_str)
            if conversation_id and belief.conversation_id != conversation_id:
                continue
            beliefs.append(belief)
        return beliefs

    async def search_beliefs(
        self,
        session_id: str,
        embedding: list[float],
        threshold: float = 0.0,
        limit: int = 5,
        conversation_id: str | None = None,
    ) -> list[Any]:
        if HAS_FAISS:
            return await self._search_beliefs_faiss(
                session_id, embedding, threshold, limit, conversation_id
            )

        # Fallback: O(n) linear scan over all beliefs in session
        beliefs = await self.get_beliefs(session_id, conversation_id)
        scored_beliefs = []

        for b in beliefs:
            if not b.embedding or not embedding:
                continue
            if len(b.embedding) != len(embedding):
                continue
            sim = cosine_similarity(b.embedding, embedding)
            if sim >= threshold:
                scored_beliefs.append((b, sim))

        scored_beliefs.sort(key=lambda x: x[1], reverse=True)
        return [sb[0] for sb in scored_beliefs[:limit]]

    async def _search_beliefs_faiss(
        self,
        session_id: str,
        embedding: list[float],
        threshold: float = 0.0,
        limit: int = 5,
        conversation_id: str | None = None,
    ) -> list[Any]:
        """FAISS-accelerated vector search over beliefs in a Redis session.

        FAISS index is built on-the-fly from belief embeddings and used to
        find the top-`limit` nearest neighbors above `threshold`.
        """
        beliefs = await self.get_beliefs(session_id, conversation_id)
        if not beliefs:
            return []

        import numpy as np

        dimension = len(embedding)
        index = faiss.IndexFlatL2(dimension)
        vectors = []
        belief_list = []

        for b in beliefs:
            if not b.embedding or len(b.embedding) != dimension:
                continue
            vectors.append(b.embedding)
            belief_list.append(b)

        if not vectors:
            return []

        ids = list(range(len(vectors)))
        matrix = np.array(vectors, dtype="float32")
        index.add(matrix)

        # Query with the new embedding
        query = np.array([embedding], dtype="float32")
        distances, indices = index.search(query, min(limit, len(vectors)))

        results = []
        for idx in indices[0]:
            if idx < 0:
                continue
            sim = 1.0 / (1.0 + distances[0][idx])  # convert L2 distance to similarity
            if sim >= threshold:
                results.append(belief_list[idx])

        return results

    def _get_audit_key(self, session_id: str, subject: str, predicate: str) -> str:
        return f"beliefstate:audit:{session_id}:{subject}::{predicate}"

    async def get_by_key(
        self,
        subject: str,
        predicate: str,
        session_id: str,
        conversation_id: str | None = None,
    ) -> Any | None:
        """Retrieve a single belief by its composite key using direct hash lookup (O(1))."""
        if not self._client:
            raise RuntimeError(
                "redis package is not installed. Run `pip install redis`"
            )
        cid = conversation_id or ""
        field = f"{subject.lower()}::{predicate.lower()}::{cid}"
        value_bytes = await self._client.hget(self._get_key(session_id), field)
        if value_bytes is None:
            return None
        if isinstance(value_bytes, bytes):
            value_str = value_bytes.decode("utf-8")
        else:
            value_str = value_bytes
        return Belief.model_validate_json(value_str)

    async def upsert(self, belief: Any) -> bool:
        """Insert or update a belief with turn-based optimistic concurrency.

        Returns True if written, False if discarded (stale write).
        """
        existing = await self.get_by_key(
            belief.subject or "",
            belief.predicate or "",
            belief.session_id or "",
            belief.conversation_id or "",
        )
        if existing and existing.turn > belief.turn:
            return False
        await self.add_belief(belief.session_id or "", belief)
        return True

    async def remove_belief(
        self,
        session_id: str,
        subject: str,
        predicate: str,
        conversation_id: str | None = None,
    ) -> None:
        if not self._client:
            raise RuntimeError(
                "redis package is not installed. Run `pip install redis`"
            )

        cid = conversation_id or ""
        field = f"{subject.lower()}::{predicate.lower()}::{cid}"
        await self._client.hdel(self._get_key(session_id), field)

    async def update_belief(self, session_id: str, belief: Any) -> None:
        await self.add_belief(session_id, belief)

    async def clear(self, session_id: str) -> None:
        if not self._client:
            raise RuntimeError(
                "redis package is not installed. Run `pip install redis`"
            )

        await self._client.delete(self._get_key(session_id))

    async def belief_count(self, session_id: str) -> int:
        if not self._client:
            raise RuntimeError(
                "redis package is not installed. Run `pip install redis`"
            )
        return int(await self._client.hlen(self._get_key(session_id)))

    async def health_check(self) -> bool:
        try:
            if not self._client:
                return False
            return bool(await self._client.ping())
        except Exception:
            return False

    async def set_session_ttl(self, session_id: str, ttl_seconds: int) -> None:
        if not self._client:
            raise RuntimeError(
                "redis package is not installed. Run `pip install redis`"
            )
        key = self._get_key(session_id)
        await self._client.expire(key, ttl_seconds)

    async def get_session_ttl(self, session_id: str) -> int | None:
        """Return TTL in seconds for a session's key.

        Returns:
            TTL in seconds if key exists and has an expiry.
            -1 if key exists but has no expiry set.
            None if key does not exist.
        """
        if not self._client:
            raise RuntimeError(
                "redis package is not installed. Run `pip install redis`"
            )
        key = self._get_key(session_id)
        ttl = await self._client.ttl(key)
        if ttl == -2:
            return None  # Key does not exist
        return int(ttl)  # -1 (no expiry) or positive TTL

    async def get_all_session_ids(self) -> list[str]:
        if not self._client:
            return []
        keys = await self._client.keys("beliefstate:session:*")
        prefix = len("beliefstate:session:")
        ids = []
        for key in keys:
            if isinstance(key, bytes):
                ids.append(key.decode()[prefix:])
            else:
                ids.append(key[prefix:])
        return ids

    async def get_audit_history(
        self,
        session_id: str,
        subject: str,
        predicate: str,
    ) -> list[dict[str, Any]]:
        """Return audit trail for a specific belief (Redis implementation stores as list)."""
        if not self._client:
            return []
        key = self._get_audit_key(session_id, subject, predicate)
        data = await self._client.lrange(key, 0, -1)

        results = []
        for item in data:
            if isinstance(item, bytes):
                item = item.decode("utf-8")
            results.append(json.loads(item))
        return results

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()
