"""
LegalCompass — ChromaDB Vector Store

Collection: legal_corpus_v1
Stores: chunk text, embedding, full metadata.
"""

from __future__ import annotations
import os
import chromadb
from chromadb.config import Settings
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "legal_corpus_v1")

_client: Optional[chromadb.PersistentClient] = None
_collection = None


def _get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=CHROMA_DB_PATH,
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def get_collection(create_if_missing: bool = True):
    global _collection
    if _collection is not None:
        return _collection
    client = _get_client()
    existing = [c.name for c in client.list_collections()]
    if COLLECTION_NAME in existing:
        _collection = client.get_collection(COLLECTION_NAME)
    elif create_if_missing:
        _collection = client.create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    else:
        raise RuntimeError(f"Collection '{COLLECTION_NAME}' not found. Run ingest first.")
    return _collection


def add_chunks(chunks: list[dict], embeddings: list[list[float]]):
    """
    Add chunks to ChromaDB.
    chunks: list of dicts with keys: id, text, metadata
    embeddings: matching list of float vectors
    """
    col = get_collection()
    ids = [c["id"] for c in chunks]
    texts = [c["text"] for c in chunks]
    metadatas = [c["metadata"] for c in chunks]
    col.add(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)


def query_collection(
    query_embedding: list[float],
    n_results: int = 5,
    where: Optional[dict] = None,
) -> dict:
    """
    Query by embedding vector.
    Returns ChromaDB result dict with ids, documents, metadatas, distances.
    """
    col = get_collection(create_if_missing=False)
    kwargs = dict(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )
    if where:
        kwargs["where"] = where
    return col.query(**kwargs)


def collection_count() -> int:
    col = get_collection(create_if_missing=False)
    return col.count()


def delete_collection():
    """Delete the collection (for full rebuild)."""
    global _collection
    client = _get_client()
    existing = [c.name for c in client.list_collections()]
    if COLLECTION_NAME in existing:
        client.delete_collection(COLLECTION_NAME)
        print(f"[vector_store] Deleted collection: {COLLECTION_NAME}")
    _collection = None


def collection_exists() -> bool:
    client = _get_client()
    existing = [c.name for c in client.list_collections()]
    return COLLECTION_NAME in existing
