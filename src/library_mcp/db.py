"""ChromaDB wrapper for vector storage and retrieval."""

from __future__ import annotations

import logging
from pathlib import Path

import chromadb

from .models import Chunk, SearchResult

logger = logging.getLogger(__name__)

COLLECTION_NAME = "library"


class VectorDB:
    """Wrapper around ChromaDB for the library collection."""

    def __init__(self, db_path: str | Path = "./db"):
        db_path = Path(db_path)
        db_path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(db_path))
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"ChromaDB initialized at {db_path}, collection has {self._collection.count()} documents")

    @property
    def collection(self):
        return self._collection

    def add_chunks(
        self,
        chunks: list[Chunk],
        embeddings: list[list[float]],
        file_hash: str,
        version_tag: str | None = None,
        ingested_at: str | None = None,
    ) -> None:
        """Add chunks with their embeddings to the collection."""
        if not chunks:
            return

        ids = [f"{file_hash}_{c.chunk_index}" for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [
            {
                "book_title": c.book_title,
                "author": c.author,
                "section_title": c.section_title,
                "chunk_index": c.chunk_index,
                "page_number": c.page_number or -1,  # ChromaDB needs non-None
                "file_hash": file_hash,
                "version_tag": version_tag or "",
                "ingested_at": ingested_at or "",
            }
            for c in chunks
        ]

        # ChromaDB has a batch limit; add in batches of 5000
        batch_size = 5000
        for i in range(0, len(ids), batch_size):
            end = i + batch_size
            self._collection.add(
                ids=ids[i:end],
                documents=documents[i:end],
                embeddings=embeddings[i:end],
                metadatas=metadatas[i:end],
            )

        logger.info(f"Added {len(chunks)} chunks for hash {file_hash[:12]}...")

    def delete_by_hash(self, file_hash: str) -> int:
        """Delete all chunks associated with a file hash. Returns count deleted."""
        # Get matching IDs first
        results = self._collection.get(where={"file_hash": file_hash})
        count = len(results["ids"])
        if count > 0:
            self._collection.delete(ids=results["ids"])
            logger.info(f"Deleted {count} chunks for hash {file_hash[:12]}...")
        return count

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        book_filter: str | None = None,
    ) -> list[SearchResult]:
        """Semantic search across the library."""
        where = {"book_title": book_filter} if book_filter else None

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self._collection.count() or 1),
            where=where,
        )

        if not results["documents"] or not results["documents"][0]:
            return []

        search_results = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            search_results.append(SearchResult(
                text=doc,
                book_title=meta["book_title"],
                author=meta["author"],
                section=meta["section_title"],
                page=meta["page_number"] if meta["page_number"] != -1 else None,
                relevance_score=round(1 - dist, 3),
            ))

        return search_results

    def get_chapter(self, book_title: str, section_title: str) -> list[dict]:
        """Retrieve all chunks from a specific section, in reading order."""
        results = self._collection.get(
            where={
                "$and": [
                    {"book_title": book_title},
                    {"section_title": section_title},
                ]
            }
        )

        if not results["documents"]:
            return []

        paired = sorted(
            zip(results["documents"], results["metadatas"]),
            key=lambda x: x[1]["chunk_index"],
        )

        return [
            {"text": doc, "chunk_index": meta["chunk_index"]}
            for doc, meta in paired
        ]

    def get_all_book_titles(self) -> list[str]:
        """Get distinct book titles in the collection."""
        if self._collection.count() == 0:
            return []
        results = self._collection.get(include=["metadatas"])
        titles = sorted({m["book_title"] for m in results["metadatas"]})
        return titles

    def count(self) -> int:
        return self._collection.count()

    def reset(self) -> None:
        """Delete and recreate the collection."""
        self._client.delete_collection(COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("Collection reset")
