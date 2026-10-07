"""
LegalCompass — Document Drafter Node

Produces draft documents using deterministic templates.
Only drafts when the user requested it.
"""
from __future__ import annotations
from agent.state import LegalCompassState
from agent.services.drafting_templates import select_and_draft


def document_drafter(state: LegalCompassState) -> LegalCompassState:
    case_analysis = state.get("case_analysis", {})
    desires_draft = case_analysis.get("desires_draft_document", False)
    draft_requested = state.get("draft_requested", False)

    if not (desires_draft or draft_requested):
        state["draft_document"] = None
        return state

    try:
        doc_type = case_analysis.get("desired_document_type", "salary_notice")
        selected_evidence = state.get("selected_evidence", [])
        authority = state.get("authority")

        result = select_and_draft(
            document_type=doc_type or "salary_notice",
            case_analysis=case_analysis,
            selected_evidence=selected_evidence,
            authority=authority,
        )
        state["draft_document"] = result
    except Exception as e:
        print(f"[document_drafter] Error: {e}")
        state["draft_document"] = None

    return state
