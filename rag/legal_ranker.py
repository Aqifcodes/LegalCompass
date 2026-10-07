"""
LegalCompass — Legal Reranker

Scores retrieved chunks for legal relevance beyond pure semantic similarity.

Considers:
- semantic similarity score (from vector search)
- legal concept match (issue-type keywords)
- section title relevance
- document relevance for query type
- worker category match
- provision type (substantive / procedural / penalty / remedy)
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Legal concept keyword maps
# ---------------------------------------------------------------------------

ISSUE_KEYWORDS: dict[str, list[str]] = {
    "unpaid_salary": [
        "unpaid wages", "payment of wages", "time limit", "wage payment",
        "wages not paid", "salary", "wages due", "disbursement",
    ],
    "delayed_salary": [
        "delay", "time limit for payment", "seventh day", "tenth day",
        "wage period", "payment date",
    ],
    "termination": [
        "termination", "dismissal", "retrenchment", "discharge",
        "standing orders", "notice period", "lay-off",
    ],
    "maternity": [
        "maternity benefit", "maternity leave", "pregnancy", "delivery",
        "nursing break", "crèche",
    ],
    "provident_fund": [
        "provident fund", "PF", "EPF", "employee provident",
        "provident fund contribution", "PF withdrawal",
    ],
    "gratuity": [
        "gratuity", "five years", "continuous service", "payment of gratuity",
    ],
    "contract_labour": [
        "contract labour", "contractor", "principal employer", "workman",
        "contract worker",
    ],
    "workplace_safety": [
        "safety", "health", "working conditions", "factory", "occupational",
        "accident", "injury",
    ],
    "dispute": [
        "industrial dispute", "conciliation", "arbitration", "tribunal",
        "labour court", "reference",
    ],
    "penalty": [
        "penalty", "offence", "prosecution", "fine", "imprisonment",
        "punishable", "conviction",
    ],
    "remedy": [
        "claim", "recovery", "application", "aggrieved", "entitlement",
        "compensation", "dues",
    ],
    "enforcement": [
        "inspector", "authority", "enforcement", "complaint", "competent authority",
        "facilitate",
    ],
    "free_legal_aid": [
        "legal aid", "legal services", "NALSA", "SALSA", "Lok Adalat",
        "free legal",
    ],
}

PROVISION_TYPE_KEYWORDS: dict[str, list[str]] = {
    "substantive": ["shall pay", "entitled to", "right to", "duty of", "obligation"],
    "procedural": ["application", "shall be made", "procedure", "form", "submit", "file"],
    "penalty": ["penalty", "fine", "imprisonment", "punishable", "offence"],
    "remedy": ["claim", "recovery", "compensation", "aggrieved person", "entitled to claim"],
    "enforcement": ["inspector", "authority", "power to", "competent authority"],
}

# Documents most relevant for each issue type
ISSUE_DOCUMENT_PREFERENCE: dict[str, list[str]] = {
    "unpaid_salary": ["COW_2019", "COW_CR_2026", "LABOUR_FAQ_2026"],
    "delayed_salary": ["COW_2019", "COW_CR_2026", "LABOUR_FAQ_2026"],
    "termination": ["IRC_2020", "IRC_CR_2026", "LABOUR_FAQ_2026"],
    "maternity": ["CSS_2020", "CSS_CR_2026", "LABOUR_FAQ_2026"],
    "provident_fund": ["CSS_2020", "CSS_CR_2026", "LABOUR_FAQ_2026"],
    "gratuity": ["CSS_2020", "CSS_CR_2026", "LABOUR_FAQ_2026"],
    "contract_labour": ["OSHWC_2020", "OSHWC_CR_2026", "COW_2019"],
    "workplace_safety": ["OSHWC_2020", "OSHWC_CR_2026"],
    "dispute": ["IRC_2020", "IRC_CR_2026"],
    "free_legal_aid": ["LSAA_1987", "NALSA_INFO"],
}


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

@dataclass
class RankedChunk:
    text: str
    document_id: str
    document_title: str
    section_number: Optional[str]
    section_title: Optional[str]
    page: Optional[int]
    source_url: Optional[str]
    jurisdiction: Optional[str]
    document_type: Optional[str]
    similarity_score: float
    legal_score: float
    combined_score: float
    provision_types: list[str] = field(default_factory=list)


def compute_legal_score(
    chunk_text: str,
    chunk_metadata: dict,
    issue_types: list[str],
    query_categories: list[str],  # substantive/procedural/remedy/enforcement/penalty
) -> tuple[float, list[str]]:
    """
    Compute a legal relevance score (0-1) for a chunk.
    Returns (score, detected_provision_types).
    """
    text_lower = chunk_text.lower()
    section_title_lower = (chunk_metadata.get("section_title") or "").lower()
    document_id = chunk_metadata.get("document_id", "")
    score = 0.0

    # 1. Issue keyword match in text (max 0.30)
    issue_score = 0.0
    for issue in issue_types:
        keywords = ISSUE_KEYWORDS.get(issue, [])
        for kw in keywords:
            if kw.lower() in text_lower:
                issue_score += 0.05
    issue_score = min(issue_score, 0.30)
    score += issue_score

    # 2. Section title match (max 0.20)
    title_score = 0.0
    for issue in issue_types:
        for kw in ISSUE_KEYWORDS.get(issue, []):
            if kw.lower() in section_title_lower:
                title_score += 0.10
    title_score = min(title_score, 0.20)
    score += title_score

    # 3. Document preference for this issue (max 0.20)
    doc_score = 0.0
    for issue in issue_types:
        preferred_docs = ISSUE_DOCUMENT_PREFERENCE.get(issue, [])
        if document_id in preferred_docs:
            position = preferred_docs.index(document_id)
            doc_score = max(doc_score, 0.20 - (position * 0.05))
    score += doc_score

    # 4. Provision type match with query categories (max 0.30)
    detected_types = []
    ptype_score = 0.0
    for ptype, keywords in PROVISION_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                detected_types.append(ptype)
                if ptype in query_categories:
                    ptype_score += 0.10
                break
    ptype_score = min(ptype_score, 0.30)
    score += ptype_score

    return min(score, 1.0), list(set(detected_types))


def rerank(
    candidates: list[dict],
    issue_types: list[str],
    query_categories: list[str],
    similarity_weight: float = 0.5,
    legal_weight: float = 0.5,
) -> list[RankedChunk]:
    """
    Rerank a list of candidate chunks (from ChromaDB query results).
    Each candidate: {text, metadata, similarity_score}
    Returns sorted list of RankedChunk, best first.
    """
    ranked = []
    for cand in candidates:
        text = cand["text"]
        meta = cand["metadata"]
        similarity = cand.get("similarity_score", 0.0)

        legal_score, provision_types = compute_legal_score(
            text, meta, issue_types, query_categories
        )

        combined = (similarity_weight * similarity) + (legal_weight * legal_score)

        ranked.append(RankedChunk(
            text=text,
            document_id=meta.get("document_id", ""),
            document_title=meta.get("document_title", ""),
            section_number=meta.get("section_number") or None,
            section_title=meta.get("section_title") or None,
            page=int(meta.get("page", 0)) or None,
            source_url=meta.get("source_url") or None,
            jurisdiction=meta.get("jurisdiction") or None,
            document_type=meta.get("document_type") or None,
            similarity_score=similarity,
            legal_score=legal_score,
            combined_score=combined,
            provision_types=provision_types,
        ))

    # Penalise structurally irrelevant section types
    LOW_VALUE_TITLES = [
        "repeal and savings", "repeal", "savings", "power to make rules",
        "power of appropriate government to make rules", "power to remove difficulties",
        "bar of suits", "protection of action", "delegation of powers",
        "exemption of employer", "effect of laws", "contracting out",
        "burden of proof", "short title", "commencement",
        "artificial humidification", "humidification",
        "canteen", "creche", "first aid", "ambulance",
        "welfare officer", "safety officer", "safety committee",
        "notice of periods of work", "register of adult workers",
        "responsibility for payment of wages",  # OSHWC s55 — contract labour only
        "payment of minimum rate of wages",     # minimum wages ≠ unpaid salary
    ]
    for r in ranked:
        title_lower = (r.section_title or "").lower()
        if any(lv in title_lower for lv in LOW_VALUE_TITLES):
            r.combined_score *= 0.3  # strong penalty — push to bottom

    ranked.sort(key=lambda x: x.combined_score, reverse=True)
    return ranked


def deduplicate(ranked: list[RankedChunk], threshold: float = 0.85) -> list[RankedChunk]:
    """
    Remove near-duplicate chunks (same section in same document).
    Keeps the highest-scoring representative.
    """
    seen_sections: set[str] = set()
    result = []

    for chunk in ranked:
        # Key: document + section number (if available) or text fingerprint
        if chunk.section_number:
            key = f"{chunk.document_id}::{chunk.section_number}"
        else:
            # Use first 80 chars of text as fingerprint
            key = f"{chunk.document_id}::{chunk.text[:80]}"

        if key not in seen_sections:
            seen_sections.add(key)
            result.append(chunk)

    return result