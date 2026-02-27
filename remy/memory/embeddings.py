"""
Vector embedding store using sentence-transformers + sqlite-vec.

Lazy-loads the SentenceTransformer model on first use to avoid slow startup.
Model encode() runs in a thread executor to avoid blocking the asyncio event loop.
Falls back gracefully to FTS5 search when sqlite-vec is unavailable.
"""

import asyncio
import logging
import os
import threading
from typing import Any

from .database import SQLITE_VEC_AVAILABLE, DatabaseManager

logger = logging.getLogger(__name__)

_MODEL_NAME = "all-MiniLM-L6-v2"
_EMBEDDING_DIM = 384

# Module-level singleton + lock: prevents concurrent model initialisation from
# the thread executor, which causes "Artifact already registered" errors in the
# HuggingFace tokenizers library when two threads try to load the same
# precompiled tokenizer simultaneously.
_model_instance = None
_model_lock = threading.Lock()

# Keep the torch inductor cache in a persistent user directory rather than
# /tmp, which can fill up and break the precompile step entirely.
os.environ.setdefault(
    "TORCHINDUCTOR_CACHE_DIR",
    os.path.expanduser("~/.cache/torch/inductor"),
)


def _load_model() -> "SentenceTransformer":  # noqa: F821
    """Load and warm up the SentenceTransformer (must be called under _model_lock)."""
    from sentence_transformers import SentenceTransformer

    logger.info("Loading SentenceTransformer model: %s …", _MODEL_NAME)
    model = SentenceTransformer(_MODEL_NAME)
    # Warm-up: trigger any JIT / tokenizer precompilation now, while we still
    # hold the lock, so concurrent callers never race during first-use compile.
    model.encode("warmup", normalize_embeddings=True)
    logger.info("Model loaded and warmed up")
    return model


class EmbeddingStore:
    """Manages text embeddings in SQLite using sqlite-vec for ANN search."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    def _get_model(self):
        """Return the module-level SentenceTransformer singleton (thread-safe)."""
        global _model_instance
        if _model_instance is None:
            with _model_lock:
                if _model_instance is None:  # double-checked locking
                    _model_instance = _load_model()
        return _model_instance

    async def embed(self, text: str) -> list[float]:
        """Return a float32 embedding vector for `text` (runs in thread executor)."""
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            None,
            lambda: self._get_model().encode(text, normalize_embeddings=True).tolist(),
        )
        return embedding

    def _vec_bytes(self, embedding: list[float]) -> bytes:
        """Serialize float list to little-endian float32 bytes for sqlite-vec."""
        import struct
        return struct.pack(f"{len(embedding)}f", *embedding)

    async def upsert_embedding(
        self,
        user_id: int,
        source_type: str,
        source_id: int,
        text: str,
    ) -> int:
        """
        Store embedding for a fact, goal, or message.
        Returns the embedding row id.
        """
        vec = await self.embed(text)
        vec_bytes = self._vec_bytes(vec)

        async with self._db.get_connection() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO embeddings (user_id, source_type, source_id, content_text, model_name)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, source_type, source_id, text, _MODEL_NAME),
            )
            embedding_id = cursor.lastrowid

            if SQLITE_VEC_AVAILABLE:
                try:
                    await conn.execute(
                        "INSERT INTO embeddings_vec(rowid, embedding) VALUES (?, ?)",
                        (embedding_id, vec_bytes),
                    )
                except Exception as e:
                    logger.warning("Could not insert into embeddings_vec: %s", e)

            await conn.commit()

        return embedding_id

    async def search_similar(
        self,
        user_id: int,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Return up to `limit` most semantically similar embeddings for this user.
        Uses sqlite-vec ANN if available; falls back to returning empty list
        (caller should use FTS5 as fallback).
        """
        if not SQLITE_VEC_AVAILABLE:
            return []

        vec = await self.embed(query)
        vec_bytes = self._vec_bytes(vec)

        async with self._db.get_connection() as conn:
            try:
                rows = await conn.execute_fetchall(
                    """
                    SELECT e.id, e.source_type, e.source_id, e.content_text, ev.distance
                    FROM embeddings_vec ev
                    JOIN embeddings e ON e.id = ev.rowid
                    WHERE e.user_id = ?
                    ORDER BY ev.distance
                    LIMIT ?
                    """,
                    (user_id, limit),
                )
                return [dict(row) for row in rows]
            except Exception as e:
                logger.warning("ANN search failed: %s", e)
                return []

    async def search_similar_for_type(
        self,
        user_id: int,
        query: str,
        source_type: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """ANN search filtered to a specific source_type (fact / goal / message)."""
        if not SQLITE_VEC_AVAILABLE:
            return []

        vec = await self.embed(query)
        vec_bytes = self._vec_bytes(vec)

        async with self._db.get_connection() as conn:
            try:
                rows = await conn.execute_fetchall(
                    """
                    SELECT e.id, e.source_type, e.source_id, e.content_text, ev.distance
                    FROM embeddings_vec ev
                    JOIN embeddings e ON e.id = ev.rowid
                    WHERE e.user_id = ? AND e.source_type = ?
                    ORDER BY ev.distance
                    LIMIT ?
                    """,
                    (user_id, source_type, limit),
                )
                return [dict(row) for row in rows]
            except Exception as e:
                logger.warning("ANN search failed: %s", e)
                return []
