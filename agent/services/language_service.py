"""
LegalCompass — Language Service

Uses Sarvam AI API for:
- Language detection
- Indian language → English translation
- English → Indian language translation

Falls back to English passthrough if API key not set or request fails.
No large local translation models are downloaded.
"""

from __future__ import annotations
import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
SARVAM_BASE_URL = "https://api.sarvam.ai"

# Short codes used inside the app
SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "te": "Telugu",
    "ta": "Tamil",
    "kn": "Kannada",
    "ml": "Malayalam",
    "mr": "Marathi",
    "bn": "Bengali",
    "gu": "Gujarati",
    "pa": "Punjabi",
    "or": "Odia",
    "as": "Assamese",
}

LANGUAGE_DISPLAY_NAMES = {v: k for k, v in SUPPORTED_LANGUAGES.items()}

# Short code -> Sarvam API code
SARVAM_CODES = {
    "en": "en-IN", "hi": "hi-IN", "te": "te-IN", "ta": "ta-IN",
    "kn": "kn-IN", "ml": "ml-IN", "mr": "mr-IN", "bn": "bn-IN",
    "gu": "gu-IN", "pa": "pa-IN", "or": "od-IN", "as": "as-IN",
}


def _short(code: str) -> str:
    """'hi-IN' -> 'hi', 'od-IN' -> 'or', None -> 'en'"""
    c = (code or "en").split("-")[0].lower()
    return "or" if c == "od" else c


def _sarvam_code(code: str) -> str:
    c = _short(code)
    return SARVAM_CODES.get(c, f"{c}-IN")


# ---------------------------------------------------------------------------
# Language Detection
# ---------------------------------------------------------------------------

def detect_language(text: str) -> tuple[str, str]:
    """
    Detect the language of input text.
    Returns (language_code, language_name).
    Falls back to heuristic detection if the API fails.
    """
    if not SARVAM_API_KEY:
        return _heuristic_detect(text)

    try:
        response = requests.post(
            f"{SARVAM_BASE_URL}/text-lid",
            json={"input": text[:500]},
            headers={
                "api-subscription-key": SARVAM_API_KEY,
                "Content-Type": "application/json",
            },
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json()
            lang_code = _short(data.get("language_code", "en"))
            lang_name = SUPPORTED_LANGUAGES.get(lang_code, "Unknown")
            return lang_code, lang_name
        print(f"[language_service] Detect {response.status_code}: {response.text[:300]}")
    except Exception as e:
        print(f"[language_service] Detection failed: {e}")

    return _heuristic_detect(text)


def _heuristic_detect(text: str) -> tuple[str, str]:
    """Detect language by Unicode script. Used when the API is unavailable."""
    if re.search(r"[\u0C00-\u0C7F]", text):
        return "te", "Telugu"
    if re.search(r"[\u0900-\u097F]", text):
        return "hi", "Hindi"
    if re.search(r"[\u0B80-\u0BFF]", text):
        return "ta", "Tamil"
    if re.search(r"[\u0C80-\u0CFF]", text):
        return "kn", "Kannada"
    if re.search(r"[\u0D00-\u0D7F]", text):
        return "ml", "Malayalam"
    if re.search(r"[\u0980-\u09FF]", text):
        return "bn", "Bengali"
    if re.search(r"[\u0A80-\u0AFF]", text):
        return "gu", "Gujarati"
    if re.search(r"[\u0A00-\u0A7F]", text):
        return "pa", "Punjabi"
    if re.search(r"[\u0B00-\u0B7F]", text):
        return "or", "Odia"
    return "en", "English"


# ---------------------------------------------------------------------------
# Translation
# ---------------------------------------------------------------------------

def translate_to_english(text: str, source_lang: str) -> tuple[str, bool]:
    """
    Translate text from source_lang to English.
    Returns (translated_text, success).
    """
    if _short(source_lang) == "en":
        return text, True

    if not SARVAM_API_KEY:
        print("[language_service] SARVAM_API_KEY not set — using original text")
        return text, False

    try:
        response = requests.post(
            f"{SARVAM_BASE_URL}/translate",
            json={
                "input": text,
                "source_language_code": _sarvam_code(source_lang),
                "target_language_code": "en-IN",
                "speaker_gender": "Male",
                "mode": "formal",
                "enable_preprocessing": True,
            },
            headers={
                "api-subscription-key": SARVAM_API_KEY,
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        if response.status_code == 200:
            return response.json().get("translated_text", text), True
        print(f"[language_service] To-English {response.status_code}: {response.text[:300]}")
    except Exception as e:
        print(f"[language_service] Translation to English failed: {e}")

    return text, False


def translate_from_english(text: str, target_lang: str) -> tuple[str, bool]:
    """
    Translate text from English to target_lang.
    Returns (translated_text, success).
    """
    if _short(target_lang) == "en":
        return text, True

    if not SARVAM_API_KEY:
        print("[language_service] SARVAM_API_KEY not set")
        return text, False

    try:
        response = requests.post(
            f"{SARVAM_BASE_URL}/translate",
            json={
                "input": text,
                "source_language_code": "en-IN",
                "target_language_code": _sarvam_code(target_lang),
                "speaker_gender": "Male",
                "mode": "formal",
                "enable_preprocessing": True,
            },
            headers={
                "api-subscription-key": SARVAM_API_KEY,
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        if response.status_code == 200:
            return response.json().get("translated_text", text), True
        print(f"[language_service] From-English {response.status_code}: {response.text[:300]}")
    except Exception as e:
        print(f"[language_service] Translation from English failed: {e}")

    return text, False


def translate_response_sections(response_dict: dict, target_lang: str) -> dict:
    """
    Translate key display sections of the final response.
    Only natural-language fields, not structured metadata.
    """
    if _short(target_lang) == "en":
        return response_dict

    translated = dict(response_dict)

    def t(text: str) -> str:
        if not text:
            return text
        result, _ = translate_from_english(text, target_lang)
        return result

    if "case_summary" in translated:
        translated["case_summary"] = t(translated["case_summary"])

    if "law" in translated and isinstance(translated["law"], dict):
        law = dict(translated["law"])
        law["plain_language_summary"] = t(law.get("plain_language_summary", ""))
        translated["law"] = law

    if "application" in translated:
        translated["application"] = t(translated["application"])

    if "next_steps" in translated:
        translated["next_steps"] = [t(step) for step in translated["next_steps"]]

    if "uncertainties" in translated:
        translated["uncertainties"] = [t(u) for u in translated["uncertainties"]]

    return translated