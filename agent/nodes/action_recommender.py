from __future__ import annotations
import os, json
from agent.state import LegalCompassState
from dotenv import load_dotenv
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

ACTION_PROMPT = """You are helping an Indian worker understand practical next steps.

Based ONLY on the retrieved legal evidence and the user's situation, list 4-6 concrete next steps.

Rules:
1. Do NOT invent legal deadlines, penalty amounts, or procedures not in the evidence.
2. Do NOT cite any section numbers in action steps — you may misattribute them.
3. Put the most important action first.
4. Always include document preservation as a step.
5. Keep each step to 1-2 sentences.
6. Do NOT repeat the same step twice.

Output ONLY a JSON array of strings:
["Step 1", "Step 2", ...]

User situation: {situation}
Issue types: {issue_types}
Evidence: {evidence_summary}
Authority: {authority}"""

def action_recommender(state: LegalCompassState) -> LegalCompassState:
    case_analysis = state.get("case_analysis", {})
    selected_evidence = state.get("selected_evidence", [])
    authority = state.get("authority", {})
    issue_types = case_analysis.get("issue_type", [])

    if not GEMINI_API_KEY:
        state["recommended_actions"] = _template_actions(issue_types, authority)
        return state

    try:
        from agent.services.gemini_helper import get_gemini_model
        model = get_gemini_model()

        evidence_summary = "\n".join(
            f"- {ev.get('chunk', ev).get('document_title', '')} Section {ev.get('chunk', ev).get('section_number', 'N/A')} ({ev.get('answers_category', '')})"
            for ev in selected_evidence[:5]
        )
        auth_str = authority.get("name", "the appropriate labour authority")
        if authority.get("official_website"):
            auth_str += f" ({authority['official_website']})"

        prompt = ACTION_PROMPT.format(
            situation=case_analysis.get("case_summary", ""),
            issue_types=", ".join(issue_types),
            evidence_summary=evidence_summary or "Limited evidence retrieved",
            authority=auth_str,
        )

        response = model.generate_content(prompt)
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        actions = json.loads(raw.strip())
        state["recommended_actions"] = [str(a) for a in actions] if isinstance(actions, list) else _template_actions(issue_types, authority)

    except Exception as e:
        print(f"[action_recommender] Error: {e}")
        state["recommended_actions"] = _template_actions(issue_types, authority)

    return state

def _template_actions(issue_types, authority):
    auth_name = authority.get("name", "the appropriate labour authority")
    auth_website = authority.get("official_website", "")
    auth_conf = authority.get("confidence", "NEEDS_VERIFICATION")
    actions = []

    actions.append(
        "Preserve all relevant documents: appointment/offer letter, payslips, bank statements showing "
        "non-receipt of salary, and all written communications with your employer."
    )

    if any(t in issue_types for t in ["unpaid_salary", "delayed_salary"]):
        actions.append(
            "Send a written demand for payment of outstanding salary to your employer (HR and reporting manager) "
            "and keep proof of delivery (email read receipt or postal acknowledgement)."
        )
        if auth_conf != "NEEDS_VERIFICATION":
            actions.append(
                f"If the employer does not respond, file a formal complaint with {auth_name}."
                + (f" Website: {auth_website}" if auth_website else "")
            )
        else:
            actions.append("Identify the correct labour authority for your establishment and file a formal complaint.")

    if "termination" in issue_types:
        actions.append("If termination did not follow proper procedure, raise an industrial dispute with the appropriate conciliation officer.")

    if "provident_fund" in issue_types:
        actions.append("File a PF grievance at epfigms.gov.in or contact your regional EPFO office.")

    if "gratuity" in issue_types:
        actions.append("Send a written demand for gratuity and if unresolved, approach the appropriate authority under the Code on Social Security, 2020.")

    if "maternity" in issue_types:
        actions.append("If maternity benefits are denied, raise the matter with the appropriate authority under the Code on Social Security, 2020.")

    actions.append("For free legal assistance, contact your District Legal Services Authority (DLSA) or visit nalsa.gov.in.")

    seen, result = set(), []
    for a in actions:
        if a[:60] not in seen:
            seen.add(a[:60])
            result.append(a)
        if len(result) >= 6:
            break
    return result