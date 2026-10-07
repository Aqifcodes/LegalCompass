from __future__ import annotations
import os, json
from agent.state import LegalCompassState
from dotenv import load_dotenv
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

INTENT_SYSTEM_PROMPT = """You are a legal case analyser for Indian employment and labour law.
Extract structured facts from the user's description. 

CRITICAL RULES:
1. Extract ONLY facts explicitly stated. Do NOT infer or assume.
2. If payment frequency not stated, leave payment_frequency as null.
3. If monthly salary not stated, do not set it. If total unpaid amount stated, record as type "total_unpaid_amount" NOT "monthly_salary".
4. If employer type not stated, leave null.
5. If state/city not mentioned, leave null.
6. needs_procedure = true if user asks "what can I do" or "how do I complain".
7. needs_remedy = true if user asks what they are entitled to.
8. needs_penalty_info = true only if they ask about penalties/fines on employer.
9. desires_draft_document = true only if they ask for a notice/letter/application.

Output ONLY valid JSON, no preamble:
{
  "case_summary": "one sentence",
  "legal_domain": "employment_and_labour",
  "issue_type": ["unpaid_salary"|"delayed_salary"|"termination"|"maternity"|"provident_fund"|"gratuity"|"contract_labour"|"workplace_safety"|"dispute"|"free_legal_aid"|"other"],
  "key_facts": ["..."],
  "employment_category": null,
  "payment_frequency": null,
  "employer_name": null,
  "employer_type": null,
  "location_city": null,
  "location_state": null,
  "documents_mentioned": [],
  "dates_and_periods": [],
  "non_payment_months": null,
  "money_amounts": [{"amount": 0.0, "currency": "INR", "type": "monthly_salary"|"total_unpaid_amount"|"mentioned_amount", "description": "string", "is_calculated": false}],
  "actions_already_taken": [],
  "communication_channels_used": [],
  "harm_or_impact": null,
  "urgency_indicators": [],
  "legal_references_mentioned": [],
  "requested_help": [],
  "desires_draft_document": false,
  "desired_document_type": null,
  "missing_information": [],
  "user_question": "string",
  "needs_substantive_law": true,
  "needs_procedure": false,
  "needs_remedy": false,
  "needs_enforcement": false,
  "needs_penalty_info": false,
  "needs_authority_info": false
}"""

def analyze_intent(state: LegalCompassState) -> LegalCompassState:
    text = state.get("english_text") or state.get("original_input", "")
    context_answers = state.get("context_answers", {})
    full_input = text
    if context_answers:
        context_str = "\n".join(f"- {k}: {v}" for k, v in context_answers.items())
        full_input = f"{text}\n\nAdditional information provided:\n{context_str}"

    if not GEMINI_API_KEY:
        state["case_analysis"] = _fallback_analysis(text)
        return state

    try:
        from agent.services.gemini_helper import get_gemini_model
        model = get_gemini_model()
        prompt = f"{INTENT_SYSTEM_PROMPT}\n\nUser's description:\n{full_input}"
        response = model.generate_content(prompt)
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        state["case_analysis"] = json.loads(raw.strip())
    except Exception as e:
        print(f"[intent_analyzer] Error: {e}")
        state["case_analysis"] = _fallback_analysis(text)
    return state

def _fallback_analysis(text: str) -> dict:
    text_lower = text.lower()
    issue_types = []
    if any(w in text_lower for w in ["salary", "wage", "pay", "payment"]):
        if any(w in text_lower for w in ["not paid", "unpaid", "pending", "due"]):
            issue_types.append("unpaid_salary")
        else:
            issue_types.append("delayed_salary")
    if "terminat" in text_lower or "dismiss" in text_lower:
        issue_types.append("termination")
    if "provident fund" in text_lower or " pf " in text_lower or "epf" in text_lower:
        issue_types.append("provident_fund")
    if "gratuity" in text_lower:
        issue_types.append("gratuity")
    if "maternity" in text_lower:
        issue_types.append("maternity")
    if not issue_types:
        issue_types = ["other"]
    return {
        "case_summary": text[:120],
        "legal_domain": "employment_and_labour",
        "issue_type": issue_types,
        "key_facts": [text[:200]],
        "employment_category": None,
        "payment_frequency": None,
        "employer_name": None,
        "employer_type": None,
        "location_city": None,
        "location_state": None,
        "documents_mentioned": [],
        "dates_and_periods": [],
        "non_payment_months": None,
        "money_amounts": [],
        "actions_already_taken": [],
        "communication_channels_used": [],
        "harm_or_impact": None,
        "urgency_indicators": [],
        "legal_references_mentioned": [],
        "requested_help": ["legal information"],
        "desires_draft_document": "draft" in text_lower or "notice" in text_lower or "letter" in text_lower,
        "desired_document_type": None,
        "missing_information": ["Payment frequency", "Employer details", "Location"],
        "user_question": text[:300],
        "needs_substantive_law": True,
        "needs_procedure": "what can i do" in text_lower or "how" in text_lower,
        "needs_remedy": "entitle" in text_lower or "compensation" in text_lower,
        "needs_enforcement": False,
        "needs_penalty_info": "penalty" in text_lower or "fine" in text_lower,
        "needs_authority_info": True,
    }