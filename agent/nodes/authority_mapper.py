"""
LegalCompass — Authority Mapper Node
Calls the deterministic authority service.
"""
from __future__ import annotations
from agent.state import LegalCompassState
from agent.services.authority_service import map_authority


def authority_mapper(state: LegalCompassState) -> LegalCompassState:
    case_analysis = state.get("case_analysis", {})
    try:
        authority = map_authority(case_analysis)
        state["authority"] = authority
    except Exception as e:
        print(f"[authority_mapper] Error: {e}")
        state["authority"] = {
            "name": "Authority to be determined",
            "confidence": "NEEDS_VERIFICATION",
            "reason_for_selection": "Authority mapping failed. Please consult a lawyer or DLSA.",
            "verification_note": "Provide your state and employer type for authority identification.",
        }
    return state
