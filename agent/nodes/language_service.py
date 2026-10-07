"""
LegalCompass — Language Service Node

Detects language and translates to English for the reasoning pipeline.
"""
from __future__ import annotations
from agent.state import LegalCompassState
from agent.services.language_service import detect_language, translate_to_english


def language_service(state: LegalCompassState) -> LegalCompassState:
    text = state.get("original_input", "")

    lang_code, lang_name = detect_language(text)
    state["detected_language"] = lang_name
    state["detected_language_code"] = lang_code

    if lang_code == "en":
        state["english_text"] = text
        state["translation_confidence"] = 1.0
    else:
        translated, success = translate_to_english(text, lang_code)
        state["english_text"] = translated
        state["translation_confidence"] = 0.9 if success else 0.0

    return state
