"""
LegalCompass — Response Builder Node

Assembles the final clean API response from pipeline state.
Does NOT expose internal state or raw field names.
"""
from __future__ import annotations
from agent.state import LegalCompassState

DISCLAIMER = (
    "LegalCompass provides legal information grounded in the retrieved sources listed above. "
    "It is not a substitute for advice from a qualified lawyer or legal professional. "
    "Verify important facts, procedures, and current requirements before taking legal action. "
    "For free legal assistance, contact your District Legal Services Authority (DLSA) or visit nalsa.gov.in."
)


def response_builder(state: LegalCompassState) -> LegalCompassState:
    case_analysis = state.get("case_analysis", {})
    legal_reasoning = state.get("legal_reasoning", {})
    selected_evidence = state.get("selected_evidence", [])
    authority = state.get("authority", {})
    recommended_actions = state.get("recommended_actions", [])
    draft_document = state.get("draft_document")
    evidence_gap_notes = state.get("evidence_gap_notes", [])

    # Build sources list (clean, for UI)
    # Only show DIRECT and SUPPORTING — hide COMPLEMENTARY and IRRELEVANT from user
    sources = []
    seen_source_keys = set()
    for ev in selected_evidence:
        classification = ev.get("classification", "")
        if classification in ("IRRELEVANT", "COMPLEMENTARY"):
            continue
        chunk = ev.get("chunk", ev)
        doc_id = chunk.get("document_id", "")
        sec_num = chunk.get("section_number", "")
        key = f"{doc_id}_{sec_num}"
        if key in seen_source_keys:
            continue
        seen_source_keys.add(key)

        doc_title = chunk.get("document_title", "Unknown document")
        sec_title = chunk.get("section_title", "")
        page = chunk.get("page")
        full_text = chunk.get("text", "")
        excerpt = full_text[:250] + ("..." if len(full_text) > 250 else "")

        # Build a working search URL instead of direct indiacode/labour.gov links
        # which block direct browser access (Akamai CDN error)
        import urllib.parse
        search_query = f"{doc_title} {f'Section {sec_num}' if sec_num else ''} India"
        search_url = f"https://www.google.com/search?q={urllib.parse.quote(search_query)}"

        sources.append({
            "document": doc_title,
            "section": f"Section {sec_num}" if sec_num else None,
            "section_title": sec_title or None,
            "page": page,
            "source_url": search_url,
            "excerpt": excerpt,
            "full_text": full_text,
            "classification": ev.get("classification", ""),
        })

    # Build provisions for "What the law says"
    import urllib.parse
    provisions = []
    for prov in legal_reasoning.get("provisions", []):
        doc = prov.get("document", "")
        sec = prov.get("section", "")
        search_query = f"{doc} {f'Section {sec}' if sec else ''} India"
        search_url = f"https://www.google.com/search?q={urllib.parse.quote(search_query)}"
        provisions.append({
            "document": doc,
            "section": sec,
            "section_title": prov.get("section_title"),
            "page": prov.get("page"),
            "source_url": search_url,
            "plain_language": prov.get("plain_language", ""),
        })

    # Uncertainties — merge gap notes + reasoner uncertainties
    uncertainties = list(evidence_gap_notes) + legal_reasoning.get("uncertainties", [])
    uncertainties = list(dict.fromkeys(uncertainties))  # dedup preserving order

    result = {
        "case_summary": case_analysis.get("case_summary", ""),
        "law": {
            "plain_language_summary": legal_reasoning.get("plain_language_summary", ""),
            "provisions": provisions,
        },
        "application": legal_reasoning.get("application_to_case", ""),
        "uncertainties": uncertainties,
        "next_steps": recommended_actions,
        "authority": authority,
        "draft_document": draft_document,
        "sources": sources,
        "disclaimer": DISCLAIMER,
        "language": {
            "detected": state.get("detected_language", "English"),
            "code": state.get("detected_language_code", "en"),
        },
        "evidence_sufficient": legal_reasoning.get("evidence_sufficient", len(sources) > 0),
    }

    state["final_response"] = result
    return state