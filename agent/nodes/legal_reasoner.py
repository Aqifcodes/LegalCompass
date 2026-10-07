from __future__ import annotations
import os, json
from agent.state import LegalCompassState
from dotenv import load_dotenv
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

REASONING_PROMPT = """You are a legal information assistant for Indian employment and labour law.

RULES:
1. You are NOT the source of law. You explain the evidence provided below.
2. Do NOT invent section numbers, deadlines, penalties, or authorities not in the evidence.
3. Do NOT claim certainty when evidence is incomplete.
4. Use plain language suitable for a non-lawyer.
5. Cite which evidence supports each statement.
6. Never claim to replace a lawyer.

User situation: {situation}

Stated facts:
{facts}
{money_text}

Selected legal evidence:
{evidence_text}

Output ONLY valid JSON:
{{
  "plain_language_summary": "2-3 sentence plain summary of what the law says",
  "provisions": [
    {{"document": "title", "section": "number or null", "section_title": "title or null", "page": null, "source_url": "url or null", "plain_language": "what this says simply"}}
  ],
  "application_to_case": "2-4 sentences connecting evidence to user's specific facts. Only what evidence supports.",
  "uncertainties": ["things unclear or missing from evidence/facts"],
  "evidence_sufficient": true,
  "evidence_gap": null
}}"""

def legal_reasoner(state: LegalCompassState) -> LegalCompassState:
    case_analysis = state.get("case_analysis", {})
    selected_evidence = state.get("selected_evidence", [])

    if not selected_evidence:
        state["legal_reasoning"] = _no_evidence()
        return state

    if not GEMINI_API_KEY:
        state["legal_reasoning"] = _fallback(selected_evidence)
        return state

    try:
        from agent.services.gemini_helper import get_gemini_model
        model = get_gemini_model()

        evidence_blocks = []
        for i, ev in enumerate(selected_evidence):
            chunk = ev.get("chunk", ev)
            doc = chunk.get("document_title", "Unknown")
            sec_num = chunk.get("section_number", "")
            sec_title = chunk.get("section_title", "")
            page = chunk.get("page")
            url = chunk.get("source_url", "")
            text = chunk.get("text", "")
            classification = ev.get("classification", "")
            category = ev.get("answers_category", "")
            sec_label = f"Section {sec_num}" if sec_num else ""
            if sec_title:
                sec_label += f" - {sec_title}" if sec_label else sec_title
            evidence_blocks.append(
                f"[Evidence {i+1}] {classification} ({category})\n"
                f"Document: {doc}\nSection: {sec_label or 'N/A'}\n"
                f"Page: {page or 'N/A'}\nURL: {url or 'N/A'}\nText:\n{text[:800]}"
            )

        facts = case_analysis.get("key_facts", [])
        facts_text = "\n".join(f"- {f}" for f in facts) if facts else case_analysis.get("case_summary", "")
        money_amounts = case_analysis.get("money_amounts", [])
        money_text = ""
        if money_amounts:
            money_text = "\nMoney amounts stated:\n" + "\n".join(
                f"  - {m.get('description', '')}: Rs.{m.get('amount', 0):,.0f} (type: {m.get('type', '')})"
                for m in money_amounts
            )

        prompt = REASONING_PROMPT.format(
            situation=case_analysis.get("case_summary", ""),
            facts=facts_text,
            money_text=money_text,
            evidence_text="\n\n---\n\n".join(evidence_blocks),
        )

        response = model.generate_content(prompt)
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        state["legal_reasoning"] = json.loads(raw.strip())

    except Exception as e:
        print(f"[legal_reasoner] Error: {e}")
        state["legal_reasoning"] = _fallback(selected_evidence)

    return state

def _no_evidence():
    return {
        "plain_language_summary": "No relevant legal provisions were retrieved from the current legal corpus for your query.",
        "provisions": [],
        "application_to_case": "Without retrieved legal evidence, a grounded legal analysis cannot be provided.",
        "uncertainties": ["Relevant legal provisions not found in corpus"],
        "evidence_sufficient": False,
        "evidence_gap": "The legal corpus did not return relevant evidence for this query.",
    }

def _fallback(evidence):
    provisions = []
    for ev in evidence[:4]:
        chunk = ev.get("chunk", ev)
        provisions.append({
            "document": chunk.get("document_title", ""),
            "section": chunk.get("section_number"),
            "section_title": chunk.get("section_title"),
            "page": chunk.get("page"),
            "source_url": chunk.get("source_url"),
            "plain_language": chunk.get("text", "")[:300] + "...",
        })
    return {
        "plain_language_summary": "Relevant provisions retrieved. AI explanation temporarily unavailable — please review source provisions directly.",
        "provisions": provisions,
        "application_to_case": "Please review the retrieved provisions as they relate to your situation.",
        "uncertainties": ["Full AI analysis temporarily unavailable."],
        "evidence_sufficient": len(provisions) > 0,
        "evidence_gap": None,
    }