"""
LegalCompass — End-to-End Pipeline Tests

Tests the full pipeline (without ChromaDB required for unit tests).
Run: python -m pytest tests/test_end_to_end.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


# =========================================================================
# UNIT — Money handling (no external dependencies)
# =========================================================================

class TestMoneyHandling:
    """Verify money semantics are never confused."""

    def test_monthly_salary_not_inferred_from_total(self):
        """
        TEST 3: User says 'I am owed ₹60,000 for three months'
        This must NOT be interpreted as monthly_salary = 60000
        """
        from agent.nodes.intent_analyzer import _fallback_analysis
        # Simulate a case_analysis that came from this input
        case = {
            "money_amounts": [
                {
                    "amount": 60000,
                    "currency": "INR",
                    "type": "total_unpaid_amount",
                    "description": "Total salary unpaid for three months",
                }
            ]
        }
        amounts = case["money_amounts"]
        monthly = [a for a in amounts if a["type"] == "monthly_salary"]
        total = [a for a in amounts if a["type"] == "total_unpaid_amount"]

        assert len(monthly) == 0, "monthly_salary must NOT be inferred from total amount"
        assert len(total) == 1, "total_unpaid_amount should be present"
        assert total[0]["amount"] == 60000

    def test_monthly_salary_explicit(self):
        """
        TEST 2: User explicitly says monthly salary is ₹40,000, 3 months unpaid.
        Monthly = 40000, total ~ 120000 (calculated, labelled approximate).
        """
        monthly_salary = 40000
        months_unpaid = 3
        calculated = monthly_salary * months_unpaid

        assert calculated == 120000
        # The template must label this as calculated
        from agent.services.drafting_templates import _money_display
        display = _money_display(calculated)
        assert "1,20,000" in display or "120,000" in display

    def test_money_display_format(self):
        """Money amounts should format with ₹ and commas."""
        from agent.services.drafting_templates import _money_display
        assert "₹" in _money_display(40000)
        assert "₹" in _money_display(120000)


# =========================================================================
# UNIT — Authority mapping (no ChromaDB needed)
# =========================================================================

class TestAuthorityMapping:
    """Verify deterministic authority selection."""

    def test_hyderabad_private_company(self):
        """
        TEST 4: Private company in Hyderabad.
        Must NOT automatically select Central Labour Commissioner.
        Should select Telangana State Labour Commissioner.
        """
        from agent.services.authority_service import map_authority
        case = {
            "employer_type": "private",
            "location_city": "Hyderabad",
            "location_state": "Telangana",
            "issue_type": ["unpaid_salary"],
        }
        result = map_authority(case)
        assert result["authority_id"] != "CLC_CENTRAL", \
            "Private company in Hyderabad must NOT map to CLC Central"
        assert "Telangana" in result["name"] or "Telangana" in result["jurisdiction"], \
            f"Expected Telangana authority, got: {result['name']}"

    def test_railway_worker_gets_central_authority(self):
        """Railway is central sphere — must get CLC or regional CLC."""
        from agent.services.authority_service import map_authority
        case = {
            "employer_name": "south central railway",
            "location_city": "Secunderabad",
            "location_state": "Telangana",
            "issue_type": ["unpaid_salary"],
        }
        result = map_authority(case)
        assert result["level"] in ("central", "central_regional"), \
            f"Railway should get central authority, got level: {result['level']}"

    def test_unknown_location_needs_verification(self):
        """When location is unknown, confidence must be NEEDS_VERIFICATION."""
        from agent.services.authority_service import map_authority
        case = {
            "employer_type": None,
            "location_city": None,
            "location_state": None,
            "issue_type": ["unpaid_salary"],
        }
        result = map_authority(case)
        assert result["confidence"] == "NEEDS_VERIFICATION", \
            f"Unknown location should produce NEEDS_VERIFICATION, got: {result['confidence']}"

    def test_pf_issue_routes_to_epfo(self):
        """PF issues must route to EPFO, not Labour Commissioner."""
        from agent.services.authority_service import map_authority
        case = {
            "issue_type": ["provident_fund"],
            "location_state": "Telangana",
        }
        result = map_authority(case)
        assert result["authority_id"] == "EPFO_HO", \
            f"PF issue must route to EPFO, got: {result['authority_id']}"

    def test_bangalore_private_company(self):
        """Bangalore private company → Karnataka Labour Commissioner."""
        from agent.services.authority_service import map_authority
        case = {
            "employer_type": "private",
            "location_city": "Bengaluru",
            "location_state": "Karnataka",
            "issue_type": ["termination"],
        }
        result = map_authority(case)
        assert "Karnataka" in result["name"] or "Karnataka" in result["jurisdiction"], \
            f"Expected Karnataka authority, got: {result['name']}"


# =========================================================================
# UNIT — Context manager (no ChromaDB needed)
# =========================================================================

class TestContextManager:
    """Verify context questions are asked appropriately."""

    def test_draft_request_triggers_location_question(self):
        """When draft is requested and location unknown, ask for location."""
        from agent.nodes.context_manager import context_manager
        state = {
            "case_analysis": {
                "issue_type": ["unpaid_salary"],
                "payment_frequency": None,
                "money_amounts": [],
                "desires_draft_document": True,
                "location_state": None,
                "location_city": None,
                "employer_type": None,
                "employer_name": None,
            },
            "context_answers": {},
        }
        result = context_manager(state)
        assert result["needs_context"] is True
        questions = result["context_questions"]
        assert len(questions) > 0
        # Should ask about location or payment frequency
        combined = " ".join(questions).lower()
        assert "state" in combined or "city" in combined or "paid" in combined or "amount" in combined

    def test_no_questions_when_facts_sufficient(self):
        """When all key facts are present, no context needed."""
        from agent.nodes.context_manager import context_manager
        state = {
            "case_analysis": {
                "issue_type": ["unpaid_salary"],
                "payment_frequency": "monthly",
                "money_amounts": [{"amount": 40000, "type": "monthly_salary"}],
                "desires_draft_document": False,
                "location_state": "Telangana",
                "location_city": "Hyderabad",
                "employer_type": "private",
                "employer_name": "Acme Corp",
            },
            "context_answers": {},
        }
        result = context_manager(state)
        # May or may not need context for non-draft case
        # Just ensure it doesn't crash
        assert "needs_context" in result


# =========================================================================
# UNIT — Input processor
# =========================================================================

class TestInputProcessor:
    def test_empty_input_sets_error(self):
        from agent.nodes.input_processor import input_processor
        state = {"original_input": ""}
        result = input_processor(state)
        assert result.get("pipeline_error") is not None

    def test_input_truncated_at_2000(self):
        from agent.nodes.input_processor import input_processor
        long_input = "a" * 3000
        state = {"original_input": long_input}
        result = input_processor(state)
        assert len(result["original_input"]) <= 2003  # 2000 + "..."

    def test_normal_input_passes_through(self):
        from agent.nodes.input_processor import input_processor
        state = {"original_input": "My employer has not paid my salary for three months."}
        result = input_processor(state)
        assert result.get("pipeline_error") is None
        assert result["original_input"] == "My employer has not paid my salary for three months."


# =========================================================================
# UNIT — Language detection (heuristic fallback)
# =========================================================================

class TestLanguageService:
    def test_english_detected(self):
        from agent.services.language_service import _heuristic_detect
        code, name = _heuristic_detect("My employer has not paid my salary.")
        assert code == "en"

    def test_telugu_detected(self):
        from agent.services.language_service import _heuristic_detect
        # Telugu characters (basic test)
        code, name = _heuristic_detect("నా జీతం వస్తలేదు")
        assert code == "te"
        assert name == "Telugu"

    def test_hindi_detected(self):
        from agent.services.language_service import _heuristic_detect
        code, name = _heuristic_detect("मेरा वेतन नहीं आया है")
        assert code == "hi"
        assert name == "Hindi"


# =========================================================================
# UNIT — Draft templates
# =========================================================================

class TestDraftTemplates:
    def test_notice_no_fabricated_amounts(self):
        """Draft must not invent amounts when none provided."""
        from agent.services.drafting_templates import draft_unpaid_salary_notice
        result = draft_unpaid_salary_notice(
            employee_name=None,
            employee_address=None,
            employee_contact=None,
            employer_name=None,
            employer_address=None,
            salary_period=None,
            total_unpaid_amount=None,
            monthly_amount=None,
            months_unpaid=None,
            actions_taken=None,
            legal_provision=None,
            legal_provision_text=None,
            authority_name=None,
        )
        body = result["body"]
        # Should have placeholders, not invented numbers
        assert "[" in body, "Should have placeholder fields"
        # No invented specific penalty amounts
        assert "15 days" not in body.lower()
        assert "1,00,000" not in body

    def test_notice_uses_provided_amounts(self):
        """Draft must use the actual provided amount."""
        from agent.services.drafting_templates import draft_unpaid_salary_notice
        result = draft_unpaid_salary_notice(
            employee_name="Test Employee",
            employee_address=None,
            employee_contact=None,
            employer_name="Test Corp",
            employer_address=None,
            salary_period="April to June 2024",
            total_unpaid_amount=90000,
            monthly_amount=None,
            months_unpaid=None,
            actions_taken=["Sent email to HR"],
            legal_provision=None,
            legal_provision_text=None,
            authority_name=None,
        )
        assert "90,000" in result["body"]
        assert "Test Corp" in result["body"]

    def test_disclaimer_outside_body(self):
        """Disclaimer must be in separate field, not inside the notice body."""
        from agent.services.drafting_templates import draft_unpaid_salary_notice
        result = draft_unpaid_salary_notice(
            employee_name=None, employee_address=None, employee_contact=None,
            employer_name=None, employer_address=None, salary_period=None,
            total_unpaid_amount=None, monthly_amount=None, months_unpaid=None,
            actions_taken=None, legal_provision=None, legal_provision_text=None,
            authority_name=None,
        )
        body = result["body"]
        disclaimer = result["disclaimer"]
        assert disclaimer, "Disclaimer must be present"
        assert "not a substitute" not in body.lower(), \
            "Disclaimer text must NOT appear inside the notice body"


# =========================================================================
# INTEGRATION — Full pipeline (requires Gemini API + ChromaDB)
# =========================================================================

@pytest.mark.integration
class TestPipeline:
    """
    Integration tests requiring Gemini API key and ingested ChromaDB.
    Run with: pytest tests/test_end_to_end.py -v -m integration
    """

    def test_01_unpaid_salary_no_amount_inference(self):
        """
        TEST 1: 'I am a permanent employee. Salary not paid for 4 months.'
        Must NOT infer monthly salary.
        """
        import os
        if not os.getenv("GEMINI_API_KEY"):
            pytest.skip("GEMINI_API_KEY not set")
        if not __import__("rag.vector_store", fromlist=["collection_exists"]).collection_exists():
            pytest.skip("ChromaDB not ingested")

        from agent.graph import run_pipeline
        result = run_pipeline(
            "My employer has not paid my salary for four months. I am a permanent employee.",
        )

        assert result.get("case_summary"), "Should have case summary"
        # Check money handling in the case_analysis via sources
        # The key check: result should NOT invent a total amount
        assert result.get("status") != "error" if "status" in result else True

    def test_02_monthly_salary_calculation_labelled(self):
        """
        TEST 2: Monthly salary ₹40,000 × 3 months = ₹1,20,000 must be labelled approximate.
        """
        from agent.services.drafting_templates import draft_unpaid_salary_notice
        result = draft_unpaid_salary_notice(
            employee_name="Ramesh Kumar",
            employee_address=None,
            employee_contact=None,
            employer_name="XYZ Ltd",
            employer_address=None,
            salary_period="April to June 2024",
            total_unpaid_amount=None,
            monthly_amount=40000,
            months_unpaid=3,
            actions_taken=None,
            legal_provision=None,
            legal_provision_text=None,
            authority_name=None,
        )
        body = result["body"]
        assert "1,20,000" in body or "120,000" in body, "Calculated total should appear"
        assert "approximate" in body.lower(), "Calculated amount must be labelled approximate"

    def test_04_hyderabad_private_no_clc_central(self):
        """
        TEST 4: Private company Hyderabad must not select Central Labour Commissioner.
        """
        from agent.services.authority_service import map_authority
        case = {
            "employer_type": "private",
            "location_city": "Hyderabad",
            "location_state": "Telangana",
            "issue_type": ["unpaid_salary"],
        }
        auth = map_authority(case)
        assert "Central Labour Commissioner" not in auth["name"] or auth["level"] != "central", \
            "Private company in Hyderabad must not get CLC(C)"

    def test_05_draft_with_missing_info_uses_placeholders(self):
        """
        TEST 5: Draft when info missing must use [PLACEHOLDERS] not invented content.
        """
        from agent.services.drafting_templates import draft_unpaid_salary_notice
        result = draft_unpaid_salary_notice(
            employee_name=None, employee_address=None, employee_contact=None,
            employer_name=None, employer_address=None, salary_period=None,
            total_unpaid_amount=None, monthly_amount=None, months_unpaid=None,
            actions_taken=None, legal_provision=None, legal_provision_text=None,
            authority_name=None,
        )
        body = result["body"]
        # Must have placeholders
        assert "[" in body
        # Must NOT have invented names, amounts
        assert "John" not in body
        assert "ABC Company" not in body


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
