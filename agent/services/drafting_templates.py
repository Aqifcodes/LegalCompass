"""
LegalCompass — Document Drafting Templates

Deterministic templates only. No fabrication.
Missing fields shown as [FIELD_NAME] placeholders.
Legal basis included ONLY when retrieved evidence supports it.
Disclaimer placed OUTSIDE the notice body.
"""

from __future__ import annotations
from datetime import date
from typing import Optional


def _v(value, placeholder: str) -> str:
    """Return value if non-empty, else placeholder."""
    if value and str(value).strip():
        return str(value).strip()
    return placeholder


def _money_display(amount: float, currency: str = "INR") -> str:
    if currency == "INR":
        return f"₹{amount:,.0f}"
    return f"{currency} {amount:,.0f}"


def _as_text(x) -> str:
    """Turn a str or dict item into plain text."""
    if isinstance(x, dict):
        return " ".join(str(v) for v in x.values() if v)
    return str(x)


# ---------------------------------------------------------------------------
# Unpaid / Delayed Salary Notice
# ---------------------------------------------------------------------------

def draft_unpaid_salary_notice(
    employee_name: Optional[str],
    employee_address: Optional[str],
    employee_contact: Optional[str],
    employer_name: Optional[str],
    employer_address: Optional[str],
    salary_period: Optional[str],
    total_unpaid_amount: Optional[float],
    monthly_amount: Optional[float],
    months_unpaid: Optional[int],
    actions_taken: Optional[list[str]],
    legal_provision: Optional[str],  # e.g. "Section 17 of the Code on Wages, 2019"
    legal_provision_text: Optional[str],
    authority_name: Optional[str],
) -> dict:
    """
    Produces a legal notice for unpaid / delayed salary.
    Returns {title, body, disclaimer}.
    """
    today = date.today().strftime("%d %B %Y")

    emp = _v(employee_name, "[Employee Full Name]")
    emp_addr = _v(employee_address, "[Employee Address]")
    emp_contact = _v(employee_contact, "[Employee Contact Details — Phone / Email]")
    er = _v(employer_name, "[Employer / Company Name]")
    er_addr = _v(employer_address, "[Employer Address / Registered Office Address]")
    period = _v(salary_period, "[salary period, e.g., April 2024 to July 2024]")
    auth = _v(authority_name, "the appropriate competent authority")

    # Build amount line
    if total_unpaid_amount and total_unpaid_amount > 0:
        amount_line = f"The total outstanding amount as of this notice is {_money_display(total_unpaid_amount)} (approximate, based on the facts provided)."
    elif monthly_amount and months_unpaid:
        calculated = monthly_amount * months_unpaid
        amount_line = f"Based on my monthly salary of {_money_display(monthly_amount)} and {months_unpaid} months of non-payment, the approximate outstanding amount is {_money_display(calculated)} (approximate calculation based on supplied facts)."
    else:
        amount_line = "The exact outstanding amount is [Total Amount Due — please specify]."

    # Actions already taken
    if actions_taken:
        actions_str = "\n".join(f"  - {a}" for a in actions_taken)
        actions_block = f"I have already taken the following steps to resolve the matter:\n{actions_str}"
    else:
        actions_block = "I have attempted to resolve this matter informally with the employer without success."

    # Legal basis — only if retrieved evidence supports it
    quote = (legal_provision_text or "")[:300]
    if legal_provision_text and len(legal_provision_text) > 300:
        cut = max(quote.rfind(";"), quote.rfind("."))
        if cut > 100:
            quote = quote[:cut + 1]
        quote = quote.rstrip() + " ..."

    if legal_provision and legal_provision_text:
        legal_block = f"""Legal Basis:

This notice is issued with reference to {legal_provision}, which provides:
"{quote}"

The applicable legal requirement obligates the employer to pay wages within the prescribed period."""
    elif legal_provision:
        legal_block = f"""Legal Basis:

This notice refers to {legal_provision}, which establishes the obligation of an employer to pay wages within the prescribed time period."""
    else:
        legal_block = """Legal Basis:

Applicable provisions of Indian labour law establish an employer's obligation to pay wages to employees within the prescribed period."""

    body = f"""LEGAL NOTICE

Date: {today}

From:
{emp}
{emp_addr}
{emp_contact}

To:
{er}
{er_addr}

Subject: Demand for Payment of Outstanding Salary / Wages

Sir / Madam,

I, {emp}, am employed / was employed with {er} in the capacity of [Designation / Position].

Facts:

1. I have been employed with your establishment since [Date of Joining].
2. My salary / wages for the period {period} remain unpaid as of the date of this notice.
3. {amount_line}
4. {actions_block}

{legal_block}

Demand:

In view of the above facts and applicable legal provisions, I hereby formally demand that {er} pay the outstanding salary / wages of {amount_line.split("is ")[-1].rstrip(".")} for the period {period}, forthwith and without further delay.

Intended Next Step:

If the outstanding amount is not paid and this matter is not resolved within a reasonable time, I intend to approach {auth} or seek appropriate legal assistance for redressal of my grievance.

Yours faithfully,

{emp}
Date: {today}"""

    disclaimer = (
        "Note: This is a draft notice prepared for your reference based on the facts you provided. "
        "It should be reviewed and verified before use. Legal requirements, authorities, and procedures "
        "may vary based on your specific circumstances. Consider consulting a qualified lawyer or "
        "approaching your District Legal Services Authority (DLSA) for free legal assistance before sending."
    )

    return {"title": "Legal Notice — Demand for Payment of Outstanding Salary", "body": body, "disclaimer": disclaimer}


# ---------------------------------------------------------------------------
# General Labour Complaint Draft
# ---------------------------------------------------------------------------

def draft_labour_complaint(
    employee_name: Optional[str],
    employee_address: Optional[str],
    employer_name: Optional[str],
    issue_description: Optional[str],
    actions_taken: Optional[list[str]],
    authority_name: Optional[str],
    authority_address: Optional[str],
) -> dict:
    today = date.today().strftime("%d %B %Y")

    emp = _v(employee_name, "[Employee Full Name]")
    emp_addr = _v(employee_address, "[Employee Address]")
    er = _v(employer_name, "[Employer / Company Name]")
    issue = _v(issue_description, "[Describe the employment issue clearly]")
    auth = _v(authority_name, "The Labour Authority")
    auth_addr = _v(authority_address, "[Authority Address]")

    if actions_taken:
        actions_str = "\n".join(f"  - {a}" for a in actions_taken)
        actions_block = f"Steps already taken:\n{actions_str}"
    else:
        actions_block = "Informal resolution attempts: [Describe what steps were taken]"

    body = f"""APPLICATION / COMPLAINT

Date: {today}

To:
The {auth}
{auth_addr}

Subject: Complaint Regarding Employment Issue

Sir / Madam,

I, {emp}, residing at {emp_addr}, respectfully submit this complaint regarding the following matter:

Employer / Establishment: {er}

Description of the Issue:
{issue}

{actions_block}

I request that the matter be enquired into and appropriate action be taken in accordance with the applicable provisions of law.

I am willing to provide any further information, documents or evidence as required.

Yours faithfully,

{emp}
{emp_addr}
Date: {today}

Enclosures (attach as applicable):
1. Copy of appointment / offer letter
2. Payslips / salary slips for the relevant period
3. Bank statements showing non-credit of salary
4. Written communications with employer (emails, letters)
5. Any other relevant document"""

    disclaimer = (
        "Note: This is a draft complaint prepared for your reference. Verify the correct authority, "
        "address and required enclosures before submitting. The exact complaint format may vary by "
        "authority. Consider seeking assistance from a DLSA or trade union representative."
    )

    return {"title": "Labour Complaint / Application", "body": body, "disclaimer": disclaimer}


# ---------------------------------------------------------------------------
# Template Selector
# ---------------------------------------------------------------------------

def select_and_draft(
    document_type: str,
    case_analysis: dict,
    selected_evidence: list[dict],
    authority: Optional[dict] = None,
) -> Optional[dict]:
    """
    Select appropriate template and populate from case facts.
    Returns {title, body, disclaimer} or None.
    """
    issue_types = case_analysis.get("issue_type") or []
    if isinstance(issue_types, str):
        issue_types = [issue_types]
    money_amounts = [m for m in (case_analysis.get("money_amounts") or []) if isinstance(m, dict)]

    # Extract money amounts
    monthly_salary = None
    total_unpaid = None
    try:
        months_unpaid = int(case_analysis.get("non_payment_months") or 0) or None
    except (TypeError, ValueError):
        months_unpaid = None

    for m in money_amounts:
        mtype = m.get("type", "")
        amount = m.get("amount", 0)
        if mtype == "monthly_salary":
            monthly_salary = amount
        elif mtype in ("total_unpaid_amount", "mentioned_amount"):
            total_unpaid = amount

    # Extract best legal provision from evidence
    legal_provision = None
    legal_provision_text = None
    for ev in selected_evidence[:3]:
        chunk = ev.get("chunk", ev)  # handle both wrapped and raw
        sec_num = chunk.get("section_number")
        sec_title = chunk.get("section_title")
        doc_title = chunk.get("document_title", "")
        text = chunk.get("text", "")
        if sec_num and doc_title:
            legal_provision = f"Section {sec_num}"
            if sec_title:
                legal_provision += f" ({sec_title})"
            legal_provision += f" of the {doc_title}"
            legal_provision_text = text[:400]
            break

    auth_name = authority.get("name") if authority else None
    auth_addr = authority.get("address") if authority else None

    doc_type_lower = (document_type or "").lower()

    actions = [_as_text(a) for a in (case_analysis.get("actions_already_taken") or [])] or None

    if any(t in issue_types for t in ["unpaid_salary", "delayed_salary"]) or \
       "salary" in doc_type_lower or "wage" in doc_type_lower or "notice" in doc_type_lower:
        return draft_unpaid_salary_notice(
            employee_name=None,  # Never infer name from key_facts — always use placeholder
            employee_address=None,
            employee_contact=None,
            employer_name=case_analysis.get("employer_name"),
            employer_address=None,
            salary_period=" to ".join(_as_text(d) for d in (case_analysis.get("dates_and_periods") or [])) or None,
            total_unpaid_amount=total_unpaid,
            monthly_amount=monthly_salary,
            months_unpaid=months_unpaid,
            actions_taken=actions,
            legal_provision=legal_provision,
            legal_provision_text=legal_provision_text,
            authority_name=auth_name,
        )

    # Generic complaint
    return draft_labour_complaint(
        employee_name=None,
        employee_address=None,
        employer_name=case_analysis.get("employer_name"),
        issue_description=case_analysis.get("case_summary"),
        actions_taken=actions,
        authority_name=auth_name,
        authority_address=auth_addr,
    )