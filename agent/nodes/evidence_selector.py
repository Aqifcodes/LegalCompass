from __future__ import annotations
import os, json
from agent.state import LegalCompassState
from dotenv import load_dotenv
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

SELECTION_PROMPT = """You are a legal evidence classifier for Indian labour law.

User situation: {situation}
Issue types: {issue_types}

Classify each chunk below. Output ONLY a JSON array:
[{{"chunk_index": 0, "classification": "DIRECT"|"SUPPORTING"|"COMPLEMENTARY"|"IRRELEVANT", "relevance_reason": "brief reason", "answers_category": "substantive"|"procedural"|"remedy"|"enforcement"|"penalty"|"background"}}]

- DIRECT: directly addresses the user's specific question with an applicable provision
- SUPPORTING: helps interpret the direct provision
- COMPLEMENTARY: related but not directly answering the core question
- IRRELEVANT: mark as IRRELEVANT if any of these apply:
  * repeal or savings section
  * power to make rules section
  * bar of suits / protection sections
  * about contract labour when user is a permanent employee
  * about artificial humidification, factories machinery, or unrelated workplace topics
  * about a completely different legal subject (e.g. social security forms when question is about wage payment)
  * minimum wages when question is about non-payment of agreed salary

Chunks:
{chunks_text}"""

def evidence_selector(state: LegalCompassState) -> LegalCompassState:
    chunks = state.get("retrieved_chunks", [])
    case_analysis = state.get("case_analysis", {})

    if not chunks:
        state["selected_evidence"] = []
        state["evidence_gap_notes"] = ["No relevant legal provisions were retrieved from the corpus."]
        return state

    if not GEMINI_API_KEY:
        state["selected_evidence"] = _fallback_select(chunks, case_analysis)
        return state

    try:
        from agent.services.gemini_helper import get_gemini_model
        model = get_gemini_model()

        chunk_summaries = []
        for i, c in enumerate(chunks):
            sec = c.get("section_title") or c.get("section_number") or "Unknown"
            doc = c.get("document_title", "")
            text_preview = c.get("text", "")[:350]
            chunk_summaries.append(f"Chunk {i}: [{doc} - {sec}]\n{text_preview}")

        prompt = SELECTION_PROMPT.format(
            situation=case_analysis.get("case_summary", case_analysis.get("user_question", "")),
            issue_types=", ".join(case_analysis.get("issue_type", [])),
            chunks_text="\n\n---\n\n".join(chunk_summaries),
        )

        response = model.generate_content(prompt)
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        classifications = json.loads(raw.strip())

        selected = []
        for cl in classifications:
            idx = cl.get("chunk_index", 0)
            classification = cl.get("classification", "IRRELEVANT")
            if classification == "IRRELEVANT":
                continue
            if idx < len(chunks):
                selected.append({
                    "chunk": chunks[idx],
                    "classification": classification,
                    "relevance_reason": cl.get("relevance_reason", ""),
                    "answers_category": cl.get("answers_category", "substantive"),
                })

        if not selected:
            # Keep top 3 as supporting if everything was classified irrelevant
            for chunk in chunks[:3]:
                selected.append({"chunk": chunk, "classification": "SUPPORTING",
                                  "relevance_reason": "Best available match", "answers_category": "background"})

        state["selected_evidence"] = selected
        state["evidence_gap_notes"] = []

    except Exception as e:
        print(f"[evidence_selector] Error: {e}")
        state["selected_evidence"] = _fallback_select(chunks, case_analysis)
        state["evidence_gap_notes"] = []

    return state

def _fallback_select(chunks, case_analysis):
    selected = []
    for i, chunk in enumerate(chunks[:5]):
        text = chunk.get("text", "").lower()
        cat = "substantive"
        if any(w in text for w in ["penalty", "fine", "offence"]):
            cat = "penalty"
        elif any(w in text for w in ["application", "claim", "aggrieved"]):
            cat = "remedy"
        elif any(w in text for w in ["inspector", "authority", "complaint"]):
            cat = "enforcement"
        selected.append({"chunk": chunk, "classification": "DIRECT" if i < 2 else "SUPPORTING",
                          "relevance_reason": "Retrieved match", "answers_category": cat})
    return selected