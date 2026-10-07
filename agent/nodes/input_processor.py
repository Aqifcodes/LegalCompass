"""
LegalCompass — Input Processor Node

Sanitises and normalises raw user input.
"""
from __future__ import annotations
import re
import uuid
from agent.state import LegalCompassState


def input_processor(state: LegalCompassState) -> LegalCompassState:
    raw = state.get("original_input", "").strip()

    if not raw:
        state["pipeline_error"] = "Empty input received."
        return state

    # Basic sanitisation
    cleaned = re.sub(r"\s+", " ", raw)
    cleaned = cleaned.strip()

    # Truncate excessively long inputs (keep first 2000 chars)
    if len(cleaned) > 2000:
        cleaned = cleaned[:2000] + "..."

    state["original_input"] = cleaned
    state["session_id"] = state.get("session_id") or str(uuid.uuid4())
    state["debug_info"] = state.get("debug_info") or {}
    state["debug_info"]["input_chars"] = len(cleaned)
    state["context_answers"] = state.get("context_answers") or {}
    state["pipeline_error"] = None

    return state
