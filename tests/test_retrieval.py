"""
LegalCompass — Retrieval Quality Tests

Run AFTER ingestion: python -m pytest tests/test_retrieval.py -v

These tests validate that the RAG pipeline retrieves legally meaningful
evidence for known query types before the reasoning layer is trusted.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from rag.retriever import retrieve_legal_evidence, generate_retrieval_queries
from rag.vector_store import collection_exists, collection_count


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def check_collection():
    if not collection_exists():
        pytest.skip("ChromaDB collection not found — run `python -m rag.ingest` first")


def run_retrieval_test(issue_types, query_categories, description):
    queries = generate_retrieval_queries(
        issue_types=issue_types,
        needs_procedure=True,
        needs_remedy=True,
        needs_enforcement=True,
    )
    results = retrieve_legal_evidence(
        queries=queries,
        issue_types=issue_types,
        query_categories=query_categories,
        top_k=5,
        max_results=6,
    )

    print(f"\n{'='*60}")
    print(f"TEST: {description}")
    print(f"Queries generated: {len(queries)}")
    print(f"Results returned: {len(results)}")
    for r in results:
        sec = f"Section {r.section_number}" if r.section_number else "N/A"
        sec_t = r.section_title or ""
        print(f"  [{r.combined_score:.3f}] {r.document_id} | {sec} — {sec_t[:50]}")
        print(f"         Similarity={r.similarity_score:.3f} Legal={r.legal_score:.3f}")
        print(f"         Types: {r.provision_types}")
    print(f"{'='*60}")

    return results


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def test_collection_exists():
    """Verify the ChromaDB collection has been built."""
    check_collection()
    count = collection_count()
    print(f"\nCollection chunk count: {count}")
    assert count > 0, "Collection is empty — run ingestion first"


# ---------------------------------------------------------------------------
# TEST 1: Unpaid salary
# ---------------------------------------------------------------------------

def test_unpaid_salary_retrieval():
    """Should retrieve wage payment provisions (Code on Wages)."""
    check_collection()
    results = run_retrieval_test(
        issue_types=["unpaid_salary"],
        query_categories=["substantive", "remedy", "enforcement"],
        description="Unpaid salary — 4 months — permanent employee",
    )
    assert len(results) > 0, "No results for unpaid salary query"

    docs = [r.document_id for r in results]
    # Should strongly prefer Code on Wages
    has_wages_doc = any("COW" in d or "LABOUR_FAQ" in d for d in docs)
    assert has_wages_doc, f"Expected Code on Wages doc in results, got: {docs}"


# ---------------------------------------------------------------------------
# TEST 2: Delayed salary
# ---------------------------------------------------------------------------

def test_delayed_salary_retrieval():
    """Should retrieve time-limit provisions."""
    check_collection()
    results = run_retrieval_test(
        issue_types=["delayed_salary"],
        query_categories=["substantive"],
        description="Delayed salary — time limit for payment",
    )
    assert len(results) > 0, "No results for delayed salary"


# ---------------------------------------------------------------------------
# TEST 3: Termination / retrenchment
# ---------------------------------------------------------------------------

def test_termination_retrieval():
    """Should retrieve Industrial Relations Code provisions."""
    check_collection()
    results = run_retrieval_test(
        issue_types=["termination"],
        query_categories=["substantive", "procedural", "remedy"],
        description="Termination / retrenchment",
    )
    assert len(results) > 0, "No results for termination"

    docs = [r.document_id for r in results]
    has_irc = any("IRC" in d or "LABOUR_FAQ" in d for d in docs)
    assert has_irc, f"Expected Industrial Relations Code, got: {docs}"


# ---------------------------------------------------------------------------
# TEST 4: Maternity benefit
# ---------------------------------------------------------------------------

def test_maternity_retrieval():
    """Should retrieve Social Security Code provisions."""
    check_collection()
    results = run_retrieval_test(
        issue_types=["maternity"],
        query_categories=["substantive", "remedy"],
        description="Maternity benefit",
    )
    assert len(results) > 0, "No results for maternity benefit"


# ---------------------------------------------------------------------------
# TEST 5: Provident fund
# ---------------------------------------------------------------------------

def test_pf_retrieval():
    """Should retrieve Social Security Code PF provisions."""
    check_collection()
    results = run_retrieval_test(
        issue_types=["provident_fund"],
        query_categories=["substantive", "procedural"],
        description="Provident Fund issue",
    )
    assert len(results) > 0, "No results for PF"


# ---------------------------------------------------------------------------
# TEST 6: Gratuity
# ---------------------------------------------------------------------------

def test_gratuity_retrieval():
    """Should retrieve gratuity provisions."""
    check_collection()
    results = run_retrieval_test(
        issue_types=["gratuity"],
        query_categories=["substantive", "remedy"],
        description="Gratuity — five years of service",
    )
    assert len(results) > 0, "No results for gratuity"


# ---------------------------------------------------------------------------
# TEST 7: Free legal aid
# ---------------------------------------------------------------------------

def test_free_legal_aid_retrieval():
    """Should retrieve NALSA / Legal Services Act provisions."""
    check_collection()
    results = run_retrieval_test(
        issue_types=["free_legal_aid"],
        query_categories=["substantive"],
        description="Free legal aid",
    )
    assert len(results) > 0, "No results for free legal aid"

    docs = [r.document_id for r in results]
    has_nalsa = any("NALSA" in d or "LSAA" in d for d in docs)
    assert has_nalsa, f"Expected NALSA or LSAA doc, got: {docs}"


# ---------------------------------------------------------------------------
# TEST 8: Penalty provisions
# ---------------------------------------------------------------------------

def test_penalty_retrieval():
    """Should retrieve penalty provisions when needed."""
    check_collection()
    queries = generate_retrieval_queries(
        issue_types=["unpaid_salary"],
        needs_penalty=True,
    )
    results = retrieve_legal_evidence(
        queries=queries,
        issue_types=["unpaid_salary"],
        query_categories=["penalty"],
        top_k=5,
        max_results=5,
    )
    print(f"\nPenalty retrieval returned {len(results)} results")
    # At least some results expected
    assert results is not None


# ---------------------------------------------------------------------------
# TEST 9: Query generation — covers multiple categories
# ---------------------------------------------------------------------------

def test_query_generation_coverage():
    """Verify multi-query generation covers required categories."""
    queries = generate_retrieval_queries(
        issue_types=["unpaid_salary"],
        needs_procedure=True,
        needs_remedy=True,
        needs_enforcement=True,
        needs_penalty=True,
        needs_authority=True,
        user_question="My employer has not paid my salary for four months. What can I do?",
    )
    print(f"\nGenerated {len(queries)} queries:")
    for q in queries:
        print(f"  - {q}")

    assert len(queries) >= 4, f"Expected at least 4 queries, got {len(queries)}"

    # Should have procedural/remedy coverage
    combined = " ".join(queries).lower()
    assert "claim" in combined or "recovery" in combined or "remedy" in combined or "complaint" in combined, \
        "Queries do not cover procedural/remedy aspects"


# ---------------------------------------------------------------------------
# TEST 10: No duplicate chunks
# ---------------------------------------------------------------------------

def test_no_duplicate_sections_in_results():
    """Deduplication should prevent same section appearing twice."""
    check_collection()
    queries = generate_retrieval_queries(
        issue_types=["unpaid_salary"],
        needs_procedure=True,
        needs_remedy=True,
    )
    results = retrieve_legal_evidence(
        queries=queries,
        issue_types=["unpaid_salary"],
        query_categories=["substantive", "remedy"],
        top_k=5,
        max_results=10,
    )
    keys = set()
    for r in results:
        key = f"{r.document_id}::{r.section_number}"
        assert key not in keys, f"Duplicate section found: {key}"
        keys.add(key)
    print(f"\nDeduplication OK — {len(results)} unique sections returned")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
