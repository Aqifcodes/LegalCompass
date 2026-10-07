"""
LegalCompass — Embedding Service

Uses sentence-transformers/all-MiniLM-L6-v2 locally.
Free, lightweight, no GPU required.
Embeddings are normalized for cosine similarity.
"""

from __future__ import annotations
import numpy as np
from typing import Optional

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        print("[embed] Loading sentence-transformers/all-MiniLM-L6-v2 ...")
        _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        print("[embed] Model loaded.")
    return _model


def embed_texts(texts: list[str], normalize: bool = True) -> list[list[float]]:
    """
    Embed a list of texts.
    Returns normalized float embeddings.
    """
    model = _get_model()
    embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    if normalize:
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        embeddings = embeddings / norms
    return embeddings.tolist()


def embed_query(query: str, normalize: bool = True) -> list[float]:
    """Embed a single query string."""
    return embed_texts([query], normalize=normalize)[0]
