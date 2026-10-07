"""
LegalCompass — RAG Ingestion Pipeline

PDF → text extraction (page-aware) → section chunking → embedding → ChromaDB

Usage:
    python -m rag.ingest                     # ingest all documents
    python -m rag.ingest --rebuild           # delete and rebuild from scratch
    python -m rag.ingest --doc COW_2019      # ingest single document
"""

from __future__ import annotations
import os
import sys
import json
import hashlib
import argparse
import re
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag.chunker import LegalChunker, LegalChunk
from rag.embed import embed_texts
from rag.vector_store import add_chunks, delete_collection, collection_exists, get_collection

REGISTRY_PATH = Path(__file__).parent.parent / "data/legal_corpus/registry/corpus_registry.json"
RAW_PDF_DIR = Path(__file__).parent.parent / "data/legal_corpus/raw"
PROCESSED_DIR = Path(__file__).parent.parent / "data/legal_corpus/processed"


# ---------------------------------------------------------------------------
# PDF Text Extraction
# ---------------------------------------------------------------------------

def extract_pdf_text(pdf_path: Path) -> str:
    """
    Extract text from PDF using PyMuPDF.
    Inserts [PAGE:N] markers between pages so the chunker can track page numbers.
    """
    doc = fitz.open(str(pdf_path))
    pages_text = []
    for page_num, page in enumerate(doc, start=1):
        text = page.get_text("text")
        # Clean up excessive whitespace within a page
        text = re.sub(r"\n{3,}", "\n\n", text)
        pages_text.append(f"[PAGE:{page_num}]\n{text}")
    doc.close()
    return "\n".join(pages_text)


# ---------------------------------------------------------------------------
# Build chunk ID
# ---------------------------------------------------------------------------

def make_chunk_id(document_id: str, chunk_index: int, text: str) -> str:
    text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
    return f"{document_id}__{chunk_index:04d}__{text_hash}"


# ---------------------------------------------------------------------------
# Ingest one document
# ---------------------------------------------------------------------------

def ingest_document(doc_meta: dict, force: bool = False) -> int:
    """
    Ingest a single document from the registry.
    Returns number of chunks added.
    """
    document_id = doc_meta["document_id"]
    filename = doc_meta["filename"]
    pdf_path = RAW_PDF_DIR / filename

    if not pdf_path.exists():
        print(f"  [SKIP] PDF not found: {pdf_path}")
        return 0

    print(f"\n[ingest] Processing: {doc_meta['title']}")
    print(f"         File: {filename}")

    # Extract text
    annotated_text = extract_pdf_text(pdf_path)
    print(f"         Pages extracted: {annotated_text.count('[PAGE:')}")

    # Save processed text
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    processed_path = PROCESSED_DIR / f"{document_id}.txt"
    processed_path.write_text(annotated_text, encoding="utf-8")

    # Chunk
    chunker = LegalChunker(
        document_id=document_id,
        document_title=doc_meta["title"],
        source_url=doc_meta.get("source_url"),
        jurisdiction=doc_meta.get("jurisdiction"),
        document_type=doc_meta.get("document_type"),
    )
    chunks: list[LegalChunk] = chunker.chunk(annotated_text)
    print(f"         Chunks produced: {len(chunks)}")

    if not chunks:
        print(f"  [WARN] No chunks produced for {document_id}")
        return 0

    # Prepare for ChromaDB
    texts = [c.text for c in chunks]

    # Embed in batches of 64
    all_embeddings = []
    batch_size = 64
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        embs = embed_texts(batch)
        all_embeddings.extend(embs)
        print(f"         Embedded {min(i + batch_size, len(texts))}/{len(texts)}", end="\r")
    print()

    # Build ChromaDB records
    records = []
    for i, (chunk, emb) in enumerate(zip(chunks, all_embeddings)):
        chunk_id = make_chunk_id(document_id, i, chunk.text)
        metadata = {
            "document_id": document_id,
            "document_title": doc_meta["title"],
            "section_number": chunk.section_number or "",
            "section_title": chunk.section_title or "",
            "page": chunk.page or 0,
            "source_url": chunk.source_url or "",
            "jurisdiction": chunk.jurisdiction or "",
            "document_type": chunk.document_type or "",
            "year": doc_meta.get("year", 0),
            "topics": ",".join(doc_meta.get("topics", [])),
        }
        records.append({"id": chunk_id, "text": chunk.text, "metadata": metadata})

    add_chunks(records, all_embeddings)
    print(f"  [OK]  {len(records)} chunks added for {document_id}")
    return len(records)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LegalCompass RAG Ingestion")
    parser.add_argument("--rebuild", action="store_true", help="Delete existing collection and rebuild from scratch")
    parser.add_argument("--doc", type=str, default=None, help="Ingest only this document_id")
    args = parser.parse_args()

    # Load registry
    with open(REGISTRY_PATH) as f:
        registry = json.load(f)
    documents = registry["documents"]

    if args.rebuild:
        print("[ingest] Rebuilding: deleting existing collection...")
        delete_collection()

    if not collection_exists():
        print("[ingest] Creating new collection: legal_corpus_v1")
        get_collection(create_if_missing=True)

    if args.doc:
        docs = [d for d in documents if d["document_id"] == args.doc]
        if not docs:
            print(f"[ERROR] Document ID not found: {args.doc}")
            sys.exit(1)
    else:
        docs = documents

    total_chunks = 0
    for doc_meta in docs:
        count = ingest_document(doc_meta)
        total_chunks += count

    print(f"\n[ingest] Done. Total chunks in store: {total_chunks}")


if __name__ == "__main__":
    main()
