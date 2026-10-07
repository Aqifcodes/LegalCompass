"""
LegalCompass — Context Manager Node

Determines whether critical facts are missing that would materially change the answer.
Generates targeted clarifying questions — ONLY questions that matter.
Sets needs_context = True to pause the graph when questions are needed.
"""
from __future__ import annotations
from agent.state import LegalCompassState


# Questions that materially affect different answer types
CONTEXT_RULES = [
    {
        "condition": lambda ca: (
            any(t in ca.get("issue_type", []) for t in ["unpaid_salary", "delayed_salary"])
            and ca.get("payment_frequency") is None
            and ca.get("desires_draft_document", False)
        ),
        "question": "How often are you normally paid — monthly, weekly, or on a different schedule?",
        "key": "payment_frequency",
    },
    {
        "condition": lambda ca: (
            any(t in ca.get("issue_type", []) for t in ["unpaid_salary", "delayed_salary"])
            and not ca.get("money_amounts")
            and ca.get("desires_draft_document", False)
        ),
        "question": "What is the total amount of salary that is currently unpaid (in ₹)?",
        "key": "unpaid_amount",
    },
    {
        "condition": lambda ca: (
            any(t in ca.get("issue_type", []) for t in ["unpaid_salary", "delayed_salary", "termination"])
            and ca.get("location_state") is None
            and ca.get("location_city") is None
        ),
        "question": "Which state or city do you work in? This helps identify the correct labour authority.",
        "key": "location",
    },
    {
        "condition": lambda ca: (
            any(t in ca.get("issue_type", []) for t in ["unpaid_salary", "delayed_salary"])
            and ca.get("employer_type") is None
            and ca.get("employer_name") is None
        ),
        "question": "Is your employer a private company, a government organisation, a bank, or another type of establishment?",
        "key": "employer_type",
    },
]

# Maximum questions to ask at once (avoid overwhelming the user)
MAX_QUESTIONS = 2


def context_manager(state: LegalCompassState) -> LegalCompassState:
    case_analysis = state.get("case_analysis", {})
    context_answers = state.get("context_answers", {})

    # Check if we've already asked and received answers
    already_asked_keys = set(context_answers.keys())
    pending_questions = []

    for rule in CONTEXT_RULES:
        key = rule["key"]
        if key in already_asked_keys:
            continue
        try:
            if rule["condition"](case_analysis):
                pending_questions.append(rule["question"])
                if len(pending_questions) >= MAX_QUESTIONS:
                    break
        except Exception:
            continue

    # Merge context answers into case_analysis if any
    if context_answers:
        _apply_context_answers(case_analysis, context_answers)
        state["case_analysis"] = case_analysis

    if pending_questions:
        state["needs_context"] = True
        state["context_questions"] = pending_questions
    else:
        state["needs_context"] = False
        state["context_questions"] = []

    return state


def _apply_context_answers(case_analysis: dict, answers: dict):
    """Merge user-supplied context answers back into case_analysis."""
    if "payment_frequency" in answers:
        case_analysis["payment_frequency"] = answers["payment_frequency"]

    if "location" in answers:
        loc = answers["location"]
        # Try to extract state name
        known_states = [
            "Telangana", "Andhra Pradesh", "Maharashtra", "Karnataka",
            "Tamil Nadu", "Kerala", "Delhi", "Gujarat", "Rajasthan",
            "Uttar Pradesh", "West Bengal", "Bihar", "Odisha",
        ]
        for s in known_states:
            if s.lower() in loc.lower():
                case_analysis["location_state"] = s
                break
        if not case_analysis.get("location_state"):
            case_analysis["location_city"] = loc

    if "employer_type" in answers:
        case_analysis["employer_type"] = answers["employer_type"]

    if "unpaid_amount" in answers:
        # Parse amount
        import re
        amt_str = answers["unpaid_amount"]
        digits = re.sub(r"[^\d.]", "", amt_str)
        if digits:
            try:
                amt = float(digits)
                case_analysis.setdefault("money_amounts", []).append({
                    "amount": amt,
                    "currency": "INR",
                    "type": "total_unpaid_amount",
                    "description": f"Total unpaid amount provided by user: ₹{amt:,.0f}",
                    "is_calculated": False,
                })
            except ValueError:
                pass
