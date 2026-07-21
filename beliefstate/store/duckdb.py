import asyncio
import importlib
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from beliefstate.models import Belief
from beliefstate.store.base import Store

logger = logging.getLogger(__name__)

try:
    duckdb_module: Any = importlib.import_module("duckdb")
    HAS_DUCKDB = True
except ImportError:
    duckdb_module = None
    HAS_DUCKDB = False


class DuckDBStore(Store):
    """DuckDB-based asynchronous storage for beliefs.

    Uses DuckDB's embedded database engine with a single guarded connection.
    Supports in-memory and file-backed databases, plus native
    ``array_cosine_similarity`` for vector search.
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._conn: Optional[Any] = None
        self._lock = asyncio.Lock()

    async def open(self) -> None:
        """Open and initialize the database connection."""
        async with self._lock:
            if self._conn is not None:
                return
            if not HAS_DUCKDB or duckdb_module is None:
                raise RuntimeError(
                    "duckdb is not installed. Run `pip install duckdb` or "
                    "`pip install beliefstate[duckdb]`"
                )

            if self.db_path != ":memory:":
                parent = os.path.dirname(self.db_path)
                if parent:
                    os.makedirs(parent, exist_ok=True)

            self._conn = duckdb_module.connect(self.db_path)
            self._init_db()

    async def close(self) -> None:
        """Close the database connection."""
        async with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None

    async def __aenter__(self) -> "DuckDBStore":
        await self.open()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def _get_connection(self) -> Any:
        if self._conn is None:
            await self.open()
        return self._conn

    def _init_db(self) -> None:
        conn = self._conn
        if conn is None:
            return

        conn.execute("""
            CREATE TABLE IF NOT EXISTS beliefs (
                session_id TEXT NOT NULL,
                conversation_id TEXT NOT NULL DEFAULT '',
                subject TEXT NOT NULL,
                predicate TEXT NOT NULL,
                value TEXT NOT NULL,
                confidence DOUBLE NOT NULL,
                turn INTEGER NOT NULL,
                source TEXT NOT NULL,
                source_quote TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT '',
                embedding DOUBLE[],
                embedding_model TEXT DEFAULT '',
                embedding_dim INTEGER DEFAULT 0,
                belief_type TEXT DEFAULT 'assertion',
                is_hypothetical BOOLEAN DEFAULT FALSE,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_referenced_at TEXT DEFAULT CURRENT_TIMESTAMP,
                resolution_note TEXT NOT NULL DEFAULT '',
                UNIQUE(session_id, conversation_id, subject, predicate)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS beliefs_audit (
                session_id TEXT NOT NULL,
                conversation_id TEXT NOT NULL DEFAULT '',
                subject TEXT NOT NULL,
                predicate TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT NOT NULL,
                operation TEXT NOT NULL,
                source_quote TEXT,
                confidence DOUBLE,
                turn INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_duckdb_session ON beliefs(session_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_duckdb_conversation ON beliefs(conversation_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_duckdb_session_conversation "
            "ON beliefs(session_id, conversation_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_duckdb_session_subject "
            "ON beliefs(session_id, subject, predicate)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_duckdb_created_at ON beliefs(created_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_duckdb_last_referenced "
            "ON beliefs(last_referenced_at)"
        )

    async def _fetchall(
        self, query: str, params: tuple[Any, ...] = ()
    ) -> List[Dict[str, Any]]:
        conn = await self._get_connection()
        async with self._lock:
            result = conn.execute(query, params)
            columns = [col[0] for col in result.description]
            return [dict(zip(columns, row)) for row in result.fetchall()]

    async def _fetchone(
        self, query: str, params: tuple[Any, ...] = ()
    ) -> Optional[Dict[str, Any]]:
        rows = await self._fetchall(query, params)
        return rows[0] if rows else None

    async def _execute(self, query: str, params: tuple[Any, ...] = ()) -> None:
        conn = await self._get_connection()
        async with self._lock:
            conn.execute(query, params)

    async def _audit(
        self,
        belief: Belief,
        operation: str,
        old_value: Optional[str] = None,
    ) -> None:
        await self._execute(
            """INSERT INTO beliefs_audit
               (session_id, conversation_id, subject, predicate, old_value, new_value,
                operation, source_quote, confidence, turn)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                belief.session_id or "",
                belief.conversation_id or "",
                (belief.subject or "").lower(),
                (belief.predicate or "").lower(),
                old_value,
                belief.value,
                operation,
                getattr(belief, "source_quote", ""),
                belief.confidence,
                belief.turn,
            ),
        )

    async def add_belief(self, session_id: str, belief: Belief) -> None:
        conversation_id = belief.conversation_id or ""
        subject = (belief.subject or "").lower()
        predicate = (belief.predicate or "").lower()
        created_at = belief.created_at or datetime.now(timezone.utc)
        last_referenced_at = belief.last_referenced_at or datetime.now(timezone.utc)

        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if last_referenced_at.tzinfo is None:
            last_referenced_at = last_referenced_at.replace(tzinfo=timezone.utc)

        old_value = None
        try:
            existing = await self.get_by_key(
                subject, predicate, session_id, conversation_id
            )
            if existing:
                old_value = existing.value
        except Exception as e:
            logger.debug(f"Audit lookup failed (non-critical): {e}")

        await self._execute(
            """
            INSERT INTO beliefs (
                session_id, conversation_id, subject, predicate, value, confidence,
                turn, source, source_quote, category, embedding, embedding_model,
                embedding_dim, belief_type, is_hypothetical, created_at,
                last_referenced_at, resolution_note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id, conversation_id, subject, predicate) DO UPDATE SET
                value = excluded.value,
                confidence = excluded.confidence,
                turn = excluded.turn,
                source = excluded.source,
                source_quote = excluded.source_quote,
                category = excluded.category,
                embedding = excluded.embedding,
                embedding_model = excluded.embedding_model,
                embedding_dim = excluded.embedding_dim,
                belief_type = excluded.belief_type,
                is_hypothetical = excluded.is_hypothetical,
                created_at = excluded.created_at,
                last_referenced_at = excluded.last_referenced_at,
                resolution_note = excluded.resolution_note
            """,
            (
                session_id,
                conversation_id,
                subject,
                predicate,
                belief.value,
                belief.confidence,
                belief.turn,
                belief.source,
                getattr(belief, "source_quote", ""),
                getattr(belief, "category", ""),
                belief.embedding,
                belief.embedding_model,
                belief.embedding_dim or len(belief.embedding),
                belief.belief_type,
                belief.is_hypothetical,
                created_at.isoformat(),
                last_referenced_at.isoformat(),
                getattr(belief, "resolution_note", ""),
            ),
        )

        if old_value is not None and old_value != belief.value:
            await self._audit(belief, "contradiction_update", old_value)
        elif old_value is None:
            await self._audit(belief, "create")

    def _row_to_belief(self, row: Dict[str, Any]) -> Belief:
        def _ensure_aware(dt: datetime) -> datetime:
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt

        created_at = row["created_at"]
        last_referenced_at = row["last_referenced_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        if isinstance(last_referenced_at, str):
            last_referenced_at = datetime.fromisoformat(last_referenced_at)

        return Belief(
            subject=row["subject"],
            predicate=row["predicate"],
            value=row["value"],
            confidence=row["confidence"],
            turn=row["turn"],
            source=row["source"],
            source_quote=row["source_quote"] or "",
            category=row["category"] or "",
            embedding=row["embedding"] or [],
            embedding_model=row["embedding_model"] or "",
            embedding_dim=row["embedding_dim"] or 0,
            belief_type=row["belief_type"] or "assertion",
            is_hypothetical=bool(row["is_hypothetical"]),
            created_at=_ensure_aware(created_at)
            if created_at
            else datetime.now(timezone.utc),
            last_referenced_at=_ensure_aware(last_referenced_at)
            if last_referenced_at
            else datetime.now(timezone.utc),
            session_id=row["session_id"],
            conversation_id=row["conversation_id"],
            resolution_note=row["resolution_note"] or "",
        )

    async def get_beliefs(
        self, session_id: str, conversation_id: Optional[str] = None
    ) -> List[Belief]:
        if conversation_id:
            rows = await self._fetchall(
                """
                SELECT subject, predicate, value, confidence, turn, source,
                       source_quote, category, embedding, embedding_model,
                       embedding_dim, belief_type, is_hypothetical, created_at,
                       last_referenced_at, session_id, conversation_id,
                       resolution_note
                FROM beliefs
                WHERE session_id = ? AND conversation_id = ?
                """,
                (session_id, conversation_id),
            )
        else:
            rows = await self._fetchall(
                """
                SELECT subject, predicate, value, confidence, turn, source,
                       source_quote, category, embedding, embedding_model,
                       embedding_dim, belief_type, is_hypothetical, created_at,
                       last_referenced_at, session_id, conversation_id,
                       resolution_note
                FROM beliefs
                WHERE session_id = ?
                """,
                (session_id,),
            )
        return [self._row_to_belief(row) for row in rows]

    async def search_beliefs(
        self,
        session_id: str,
        embedding: List[float],
        threshold: float = 0.0,
        limit: int = 5,
        conversation_id: Optional[str] = None,
    ) -> List[Belief]:
        if not embedding:
            return []

        dimension = len(embedding)
        array_type = f"DOUBLE[{dimension}]"
        if conversation_id:
            rows = await self._fetchall(
                f"""
                SELECT subject, predicate, value, confidence, turn, source,
                       source_quote, category, embedding, embedding_model,
                       embedding_dim, belief_type, is_hypothetical, created_at,
                       last_referenced_at, session_id, conversation_id,
                       resolution_note,
                       array_cosine_similarity(
                           embedding::{array_type}, ?::{array_type}
                       ) AS similarity
                FROM beliefs
                WHERE session_id = ?
                  AND conversation_id = ?
                  AND embedding IS NOT NULL
                  AND array_length(embedding) = ?
                  AND embedding_dim = ?
                  AND array_cosine_similarity(
                      embedding::{array_type}, ?::{array_type}
                  ) >= ?
                ORDER BY similarity DESC
                LIMIT ?
                """,
                (
                    embedding,
                    session_id,
                    conversation_id,
                    dimension,
                    dimension,
                    embedding,
                    threshold,
                    limit,
                ),
            )
        else:
            rows = await self._fetchall(
                f"""
                SELECT subject, predicate, value, confidence, turn, source,
                       source_quote, category, embedding, embedding_model,
                       embedding_dim, belief_type, is_hypothetical, created_at,
                       last_referenced_at, session_id, conversation_id,
                       resolution_note,
                       array_cosine_similarity(
                           embedding::{array_type}, ?::{array_type}
                       ) AS similarity
                FROM beliefs
                WHERE session_id = ?
                  AND embedding IS NOT NULL
                  AND array_length(embedding) = ?
                  AND embedding_dim = ?
                  AND array_cosine_similarity(
                      embedding::{array_type}, ?::{array_type}
                  ) >= ?
                ORDER BY similarity DESC
                LIMIT ?
                """,
                (
                    embedding,
                    session_id,
                    dimension,
                    dimension,
                    embedding,
                    threshold,
                    limit,
                ),
            )
        return [self._row_to_belief(row) for row in rows]

    async def get_by_key(
        self,
        subject: str,
        predicate: str,
        session_id: str,
        conversation_id: Optional[str] = None,
    ) -> Optional[Belief]:
        row = await self._fetchone(
            """
            SELECT subject, predicate, value, confidence, turn, source,
                   source_quote, category, embedding, embedding_model,
                   embedding_dim, belief_type, is_hypothetical, created_at,
                   last_referenced_at, session_id, conversation_id, resolution_note
            FROM beliefs
            WHERE session_id = ? AND conversation_id = ?
              AND subject = ? AND predicate = ?
            LIMIT 1
            """,
            (
                session_id,
                conversation_id or "",
                subject.lower(),
                predicate.lower(),
            ),
        )
        return self._row_to_belief(row) if row else None

    async def upsert(self, belief: Belief) -> bool:
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
        conversation_id: Optional[str] = None,
    ) -> None:
        existing = await self.get_by_key(
            subject, predicate, session_id, conversation_id
        )
        if existing:
            await self._audit(existing, "delete")

        await self._execute(
            """
            DELETE FROM beliefs
            WHERE session_id = ? AND conversation_id = ?
              AND subject = ? AND predicate = ?
            """,
            (session_id, conversation_id or "", subject.lower(), predicate.lower()),
        )

    async def update_belief(self, session_id: str, belief: Belief) -> None:
        await self.add_belief(session_id, belief)

    async def clear(self, session_id: str) -> None:
        await self._execute("DELETE FROM beliefs WHERE session_id = ?", (session_id,))

    async def belief_count(self, session_id: str) -> int:
        row = await self._fetchone(
            "SELECT COUNT(*) AS count FROM beliefs WHERE session_id = ?",
            (session_id,),
        )
        return int(row["count"]) if row else 0

    async def health_check(self) -> bool:
        try:
            row = await self._fetchone("SELECT 1 AS ok")
            return bool(row and row["ok"] == 1)
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False

    async def get_all_session_ids(self) -> List[str]:
        rows = await self._fetchall(
            "SELECT DISTINCT session_id FROM beliefs ORDER BY session_id"
        )
        return [row["session_id"] for row in rows]

    async def get_audit_history(
        self,
        session_id: str,
        subject: str,
        predicate: str,
    ) -> List[Dict[str, Any]]:
        rows = await self._fetchall(
            """
            SELECT turn, old_value, new_value, operation, confidence, created_at,
                   conversation_id
            FROM beliefs_audit
            WHERE session_id = ? AND subject = ? AND predicate = ?
            ORDER BY created_at ASC
            """,
            (session_id, subject.lower(), predicate.lower()),
        )
        return rows

    async def get_all_audit_history(self, session_id: str) -> List[Dict[str, Any]]:
        return await self._fetchall(
            """
            SELECT session_id, conversation_id, subject, predicate, old_value,
                   new_value, operation, source_quote, confidence, turn, created_at
            FROM beliefs_audit
            WHERE session_id = ?
            ORDER BY created_at ASC
            """,
            (session_id,),
        )
