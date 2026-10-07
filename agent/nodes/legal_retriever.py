"""
LegalCompass — Legal Retriever Node

Runs multi-query retrieval from ChromaDB.
"""
from __future__ import annotations
from agent.state import LegalCompassState
from rag.retriever import run_retrieval, generate_retrieval_queries


def legal_retriever(state: LegalCompassState) -> LegalCompassState:
    case_analysis = state.get("case_analysis", {})

    try:
        retrieved = run_retrieval(case_analysis)
        state["retrieved_chunks"] = retrieved
        state["retrieval_queries"] = generate_retrieval_queries(
            issue_types=case_analysis.get("issue_type", []),
            needs_procedure=case_analysis.get("needs_procedure", False),
            needs_remedy=case_analysis.get("needs_remedy", False),
            needs_enforcement=case_analysis.get("needs_enforcement", False),
            needs_penalty=case_analysis.get("needs_penalty_info", False),
            needs_authority=case_analysis.get("needs_authority_info", False),
            user_question=case_analysis.get("user_question", ""),
        )
    except Exception as e:
        print(f"[legal_retriever] Retrieval error: {e}")
        state["retrieved_chunks"] = []
        state["retrieval_queries"] = []
        state["evidence_gap_notes"] = [
            "The legal retrieval system encountered an error. The response below is based on general understanding rather than retrieved source documents."
        ]

    return state
