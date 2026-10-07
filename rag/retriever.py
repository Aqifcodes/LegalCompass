"""
LegalCompass — Legal Retriever

Multi-query retrieval pipeline:
1. Generate focused sub-queries from case facts
2. Retrieve candidates for each query
3. Pool and deduplicate
4. Rerank using legal scoring
5. Return final evidence

Never relies on a single query.
Covers: substantive, procedural, remedy, enforcement, penalty, authority categories.
"""

from __future__ import annotations
import os
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from rag.embed import embed_query
from rag.vector_store import query_collection
from rag.legal_ranker import rerank, deduplicate, RankedChunk

TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "5"))
MAX_EVIDENCE = int(os.getenv("MAX_EVIDENCE_CHUNKS", "8"))


# ---------------------------------------------------------------------------
# Query templates per category
# ---------------------------------------------------------------------------

QUERY_TEMPLATES: dict[str, list[str]] = {
    "unpaid_salary": [
        "time limit for payment of wages India",
        "unpaid wages employer liability India",
        "payment of wages obligation section",
        "claims for recovery of wages India labour law",
        "penalty for non-payment of wages employer",
        "complaint authority unpaid salary worker India",
    ],
    "delayed_salary": [
        "time limit payment of wages schedule",
        "wage payment deadline employer India",
        "delay in payment of wages penalty",
        "payment period wages India labour code",
    ],
    "termination": [
        "termination of employment India labour law",
        "retrenchment procedure notice pay",
        "wrongful dismissal industrial dispute India",
        "standing orders termination employee rights",
        "termination compensation entitlement India",
    ],
    "maternity": [
        "maternity benefit entitlement India",
        "maternity leave duration paid leave",
        "maternity benefit payment employer obligation",
        "maternity benefit claim procedure",
    ],
    "provident_fund": [
        "provident fund employee contribution India",
        "EPF withdrawal claim procedure",
        "provident fund employer obligation",
        "PF grievance complaint procedure India",
        "provident fund default employer penalty",
    ],
    "gratuity": [
        "payment of gratuity India eligibility",
        "gratuity calculation five years service",
        "gratuity claim procedure employer",
        "gratuity payment default penalty India",
    ],
    "contract_labour": [
        "contract labour rights India",
        "contractor principal employer liability wages",
        "contract worker payment obligation",
    ],
    "workplace_safety": [
        "occupational safety health employer duty India",
        "workplace accident compensation India",
        "working conditions standard factory India",
    ],
    "dispute": [
        "industrial dispute resolution India",
        "conciliation officer procedure India",
        "labour court reference procedure India",
        "grievance redressal mechanism employee",
    ],
    "free_legal_aid": [
        "free legal aid worker India eligibility",
        "NALSA legal services worker",
        "Lok Adalat industrial dispute",
    ],
}

# Generic retrieval queries always included
BASE_QUERIES = [
    "appropriate authority complaint labour India",
    "worker rights remedy India employment",
]


# ---------------------------------------------------------------------------
# Query generator
# ---------------------------------------------------------------------------

def generate_retrieval_queries(
    issue_types: list[str],
    needs_procedure: bool = False,
    needs_remedy: bool = False,
    needs_enforcement: bool = False,
    needs_penalty: bool = False,
    needs_authority: bool = False,
    user_question: str = "",
) -> list[str]:
    """
    Generate focused retrieval queries from case facts.
    Always covers substantive + selectively adds procedure/remedy/enforcement.
    """
    queries: list[str] = []

    for issue in issue_types:
        templates = QUERY_TEMPLATES.get(issue, [])
        queries.extend(templates[:3])  # top 3 per issue (substantive focus)

        if needs_procedure or needs_remedy or needs_enforcement:
            queries.extend(templates[3:])  # include procedural/remedy queries

    # Always add authority query when needed
    if needs_authority:
        queries.extend(BASE_QUERIES)

    # Add the raw user question as an additional query
    if user_question and len(user_question) > 10:
        queries.append(user_question[:200])

    # Deduplicate while preserving order
    seen = set()
    result = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            result.append(q)

    return result


# ---------------------------------------------------------------------------
# Query categories from case analysis
# ---------------------------------------------------------------------------

def get_query_categories(case_analysis: dict) -> list[str]:
    """Map case_analysis boolean flags to category labels for the reranker."""
    cats = []
    if case_analysis.get("needs_substantive_law", True):
        cats.append("substantive")
    if case_analysis.get("needs_procedure", False):
        cats.append("procedural")
    if case_analysis.get("needs_remedy", False):
        cats.append("remedy")
    if case_analysis.get("needs_enforcement", False):
        cats.append("enforcement")
    if case_analysis.get("needs_penalty_info", False):
        cats.append("penalty")
    if case_analysis.get("needs_authority_info", False):
        cats.append("enforcement")  # authority = enforcement category
    return list(set(cats)) or ["substantive"]


# ---------------------------------------------------------------------------
# Main retrieval function
# ---------------------------------------------------------------------------

def retrieve_legal_evidence(
    queries: list[str],
    issue_types: list[str],
    query_categories: list[str],
    top_k: int = TOP_K,
    max_results: int = MAX_EVIDENCE,
) -> list[RankedChunk]:
    """
    Run multi-query retrieval, pool results, rerank, deduplicate.
    Returns final ranked evidence list (up to max_results).
    """
    all_candidates: dict[str, dict] = {}  # chunk_id → candidate

    for query in queries:
        try:
            qvec = embed_query(query)
            results = query_collection(qvec, n_results=top_k)
        except Exception as e:
            print(f"[retriever] Query failed: {query[:50]} — {e}")
            continue

        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for cid, doc, meta, dist in zip(ids, docs, metas, distances):
            if cid not in all_candidates:
                # ChromaDB cosine distance: 0=identical, 2=opposite
                # Convert to similarity: 1 - (dist/2)
                similarity = max(0.0, 1.0 - (dist / 2.0))
                all_candidates[cid] = {
                    "id": cid,
                    "text": doc,
                    "metadata": meta,
                    "similarity_score": similarity,
                }

    if not all_candidates:
        return []

    candidates = list(all_candidates.values())
    ranked = rerank(candidates, issue_types, query_categories)
    deduped = deduplicate(ranked)
    return deduped[:max_results]


# ---------------------------------------------------------------------------
# High-level interface called from the pipeline
# ---------------------------------------------------------------------------

def run_retrieval(case_analysis: dict) -> list[dict]:
    """
    Full retrieval given a serialized CaseAnalysis.
    Returns list of serialized RankedChunk dicts.
    """
    issue_types = case_analysis.get("issue_type", ["unpaid_salary"])
    user_question = case_analysis.get("user_question", "")

    queries = generate_retrieval_queries(
        issue_types=issue_types,
        needs_procedure=case_analysis.get("needs_procedure", False),
        needs_remedy=case_analysis.get("needs_remedy", False),
        needs_enforcement=case_analysis.get("needs_enforcement", False),
        needs_penalty=case_analysis.get("needs_penalty_info", False),
        needs_authority=case_analysis.get("needs_authority_info", False),
        user_question=user_question,
    )

    query_categories = get_query_categories(case_analysis)

    ranked = retrieve_legal_evidence(
        queries=queries,
        issue_types=issue_types,
        query_categories=query_categories,
    )

    return [
        {
            "chunk_id": f"{c.document_id}_{i}",
            "text": c.text,
            "document_id": c.document_id,
            "document_title": c.document_title,
            "section_number": c.section_number,
            "section_title": c.section_title,
            "page": c.page,
            "source_url": c.source_url,
            "jurisdiction": c.jurisdiction,
            "document_type": c.document_type,
            "similarity_score": round(c.similarity_score, 4),
            "legal_score": round(c.legal_score, 4),
        }
        for i, c in enumerate(ranked)
    ]
