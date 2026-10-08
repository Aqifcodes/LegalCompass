"""
LegalCompass — Translation endpoint
POST /api/translate
Input: {result, target_lang, target_lang_name}
Returns: {status, translated_result}
"""
import re
from concurrent.futures import ThreadPoolExecutor

from flask import Blueprint, request, jsonify
from agent.services.language_service import translate_from_english

translate_bp = Blueprint("translate", __name__)

MAX_CHARS = 900
WORKERS = 4


def chunk(text):
    parts, cur = [], ""
    for sent in re.split(r'(?<=[.!?।])\s+', text):
        if cur and len(cur) + len(sent) + 1 > MAX_CHARS:
            parts.append(cur)
            cur = sent
        else:
            cur = f"{cur} {sent}".strip()
    if cur:
        parts.append(cur)
    return parts


def _translate_plain(text, lang):
    """Translate text line by line, keeping line breaks. No protection logic."""
    lines = []
    for line in text.split("\n"):
        if not line.strip():
            lines.append(line)
            continue
        pieces = [translate_from_english(p, lang)[0] for p in chunk(line)]
        lines.append(" ".join(pieces))
    return "\n".join(lines)


def translate_text(text, lang):
    """Translate one string. Keeps line breaks, [placeholders] and quoted law in English."""
    text = str(text)
    keep_re = []
    if "Legal Basis" in text:
        keep_re.append(r'"[^"]{20,}"')      # quoted law text
    keep_re.append(r'\[[^\]\n]+\]')         # [placeholders]
    pattern = re.compile("|".join(keep_re), re.S)

    # Attempt 1: swap protected parts for tokens, translate with full context
    kept = []

    def stash(m):
        kept.append(m.group(0))
        return f"XQ{len(kept) - 1}QX"

    tokenised = pattern.sub(stash, text)
    out = _translate_plain(tokenised, lang)

    if all(f"XQ{i}QX" in out for i in range(len(kept))):
        for i, original in enumerate(kept):
            out = out.replace(f"XQ{i}QX", original)
        return out

    # Attempt 2: a token got changed, so translate only the text between protected parts
    result, last = [], 0
    for m in pattern.finditer(text):
        before = text[last:m.start()]
        result.append(_translate_plain(before, lang) if before.strip() else before)
        result.append(m.group(0))
        last = m.end()
    tail = text[last:]
    result.append(_translate_plain(tail, lang) if tail.strip() else tail)
    return "".join(result)


def build(result, t):
    """Build the translated result. t() is applied to every field to translate."""
    out = dict(result)

    out["case_summary"] = t(result.get("case_summary", ""))

    old_law = result.get("law") or {}
    law = dict(old_law)
    law["plain_language_summary"] = t(old_law.get("plain_language_summary", ""))
    provisions = []
    for prov in old_law.get("provisions", []):
        p = dict(prov)
        p["plain_language"] = t(prov.get("plain_language", ""))
        p["section_title"] = t(prov.get("section_title"))
        provisions.append(p)
    law["provisions"] = provisions
    out["law"] = law

    out["application"] = t(result.get("application", ""))
    out["uncertainties"] = [t(u) for u in result.get("uncertainties", [])]
    out["next_steps"] = [t(s) for s in result.get("next_steps", [])]

    auth = dict(result.get("authority") or {})
    for key in ("jurisdiction", "reason_for_selection", "verification_note"):
        if auth.get(key):
            auth[key] = t(auth[key])
    secondary = []
    for sa in auth.get("secondary_authorities") or []:
        s = dict(sa)
        if s.get("reason_for_selection"):
            s["reason_for_selection"] = t(s["reason_for_selection"])
        secondary.append(s)
    if secondary:
        auth["secondary_authorities"] = secondary
    out["authority"] = auth

    draft = result.get("draft_document")
    if draft:
        d = dict(draft)
        d["title"] = t(draft.get("title"))
        d["body"] = t(draft.get("body", ""))
        d["disclaimer"] = t(draft.get("disclaimer", ""))
        out["draft_document"] = d

    out["disclaimer"] = t(result.get("disclaimer", ""))
    return out


@translate_bp.route("/api/translate", methods=["POST"])
def translate_result():
    try:
        data = request.get_json(force=True)
        result = data.get("result", {})
        target_lang = data.get("target_lang", "en")

        if target_lang == "en":
            return jsonify({"status": "success", "translated_result": result})

        # Pass 1: collect every string that needs translating
        texts = []

        def collect(text):
            if text and str(text).strip() and text not in texts:
                texts.append(text)
            return text

        build(result, collect)

        # Translate them all in parallel
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            done = dict(zip(texts, pool.map(lambda x: translate_text(x, target_lang), texts)))

        # Pass 2: build the real result from the translations
        def lookup(text):
            if not text or not str(text).strip():
                return text
            return done.get(text, text)

        translated = build(result, lookup)

        if result.get("application") and translated["application"] == result["application"]:
            return jsonify({
                "status": "error",
                "error": "Translation came back unchanged. Check SARVAM_API_KEY and terminal logs."
            }), 502

        return jsonify({"status": "success", "translated_result": translated})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500