"""
LegalCompass — Agent State Models
All state passing through the LangGraph pipeline lives here.
"""

from __future__ import annotations
from typing import Any, Optional
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class EvidenceClass(str, Enum):
    DIRECT = "DIRECT"
    SUPPORTING = "SUPPORTING"
    COMPLEMENTARY = "COMPLEMENTARY"
    IRRELEVANT = "IRRELEVANT"


class MoneyType(str, Enum):
    MONTHLY_SALARY = "monthly_salary"
    TOTAL_UNPAID_AMOUNT = "total_unpaid_amount"
    MENTIONED_AMOUNT = "mentioned_amount"
    ANNUAL_SALARY = "annual_salary"
    OTHER = "other"


class JurisdictionConfidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    NEEDS_VERIFICATION = "NEEDS_VERIFICATION"


# ---------------------------------------------------------------------------
# Money Handling — strict semantics
# ---------------------------------------------------------------------------

class MoneyAmount(BaseModel):
    amount: float
    currency: str = "INR"
    type: MoneyType
    description: str
    is_calculated: bool = False
    calculation_note: Optional[str] = None


# ---------------------------------------------------------------------------
# Case Analysis — Gemini structured extraction
# ---------------------------------------------------------------------------

class CaseAnalysis(BaseModel):
    """Structured extraction of user's legal situation. No inference beyond stated facts."""
    case_summary: str = Field(description="One-sentence summary of the user's situation")
    legal_domain: str = Field(default="employment_and_labour")
    issue_type: list[str] = Field(default_factory=list, description="e.g. unpaid_salary, termination, pf_issue")
    
    # Facts — only what was explicitly stated
    key_facts: list[str] = Field(default_factory=list)
    employment_category: Optional[str] = Field(default=None, description="permanent / contract / casual — ONLY if stated")
    payment_frequency: Optional[str] = Field(default=None, description="monthly/weekly/daily — ONLY if stated")
    
    # Entities
    employer_name: Optional[str] = None
    employer_type: Optional[str] = Field(default=None, description="private/government/central_psu — ONLY if stated")
    location_city: Optional[str] = None
    location_state: Optional[str] = None
    
    # Documents / evidence
    documents_mentioned: list[str] = Field(default_factory=list)
    
    # Time
    dates_and_periods: list[str] = Field(default_factory=list)
    non_payment_months: Optional[int] = Field(default=None, description="Number of months unpaid — ONLY if explicitly stated")
    
    # Money — strict
    money_amounts: list[MoneyAmount] = Field(default_factory=list)
    
    # Communication
    actions_already_taken: list[str] = Field(default_factory=list)
    communication_channels_used: list[str] = Field(default_factory=list)
    
    # Impact
    harm_or_impact: Optional[str] = None
    urgency_indicators: list[str] = Field(default_factory=list)
    
    # Legal references the user mentioned
    legal_references_mentioned: list[str] = Field(default_factory=list)
    
    # What they want
    requested_help: list[str] = Field(default_factory=list)
    desires_draft_document: bool = False
    desired_document_type: Optional[str] = None
    
    # Missing facts that materially affect the answer
    missing_information: list[str] = Field(default_factory=list)
    
    # The core question
    user_question: str = Field(description="The user's primary question in plain language")
    
    # Categories of answer needed
    needs_substantive_law: bool = True
    needs_procedure: bool = False
    needs_remedy: bool = False
    needs_enforcement: bool = False
    needs_penalty_info: bool = False
    needs_authority_info: bool = False


# ---------------------------------------------------------------------------
# Retrieved Evidence
# ---------------------------------------------------------------------------

class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    document_id: str
    document_title: str
    section_number: Optional[str] = None
    section_title: Optional[str] = None
    page: Optional[int] = None
    source_url: Optional[str] = None
    jurisdiction: Optional[str] = None
    document_type: Optional[str] = None
    similarity_score: float = 0.0
    legal_score: float = 0.0


class EvidenceItem(BaseModel):
    chunk: RetrievedChunk
    classification: EvidenceClass
    relevance_reason: str
    answers_category: str = Field(description="substantive/procedure/remedy/enforcement/penalty/authority")


# ---------------------------------------------------------------------------
# Authority Result
# ---------------------------------------------------------------------------

class AuthorityResult(BaseModel):
    authority_id: str
    name: str
    short_name: str
    department: str
    level: str
    jurisdiction: str
    address: str
    phone: Optional[str] = None
    official_website: Optional[str] = None
    maps_url: Optional[str] = None
    reason_for_selection: str
    confidence: JurisdictionConfidence
    verification_note: Optional[str] = None
    secondary_authorities: list[dict] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Legal Source (for UI display)
# ---------------------------------------------------------------------------

class LegalSource(BaseModel):
    document_id: str
    document_title: str
    section_number: Optional[str] = None
    section_title: Optional[str] = None
    page: Optional[int] = None
    source_url: Optional[str] = None
    excerpt: str
    full_text: str


# ---------------------------------------------------------------------------
# Legal Provision (for "What the law says")
# ---------------------------------------------------------------------------

class LegalProvision(BaseModel):
    document: str
    section: Optional[str] = None
    section_title: Optional[str] = None
    page: Optional[int] = None
    plain_language: str
    source_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Final API Response Schema
# ---------------------------------------------------------------------------

class LawSection(BaseModel):
    plain_language_summary: str
    provisions: list[LegalProvision]


class ApiResponse(BaseModel):
    status: str = "success"
    needs_context: bool = False
    context_questions: list[str] = Field(default_factory=list)
    result: Optional[dict] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# LangGraph State TypedDict
# ---------------------------------------------------------------------------

class LegalCompassState(TypedDict, total=False):
    # Input
    original_input: str
    session_id: str
    
    # Language
    detected_language: str
    detected_language_code: str
    english_text: str
    translation_confidence: float
    
    # Case understanding
    case_analysis: dict  # serialized CaseAnalysis
    
    # Context completion
    needs_context: bool
    context_questions: list[str]
    context_answers: dict[str, str]
    
    # Retrieval
    retrieval_queries: list[str]
    retrieved_chunks: list[dict]  # serialized RetrievedChunk list
    
    # Evidence
    selected_evidence: list[dict]  # serialized EvidenceItem list
    evidence_gap_notes: list[str]
    
    # Reasoning
    legal_reasoning: dict  # {summary, provisions, application, uncertainties}
    
    # Authority
    authority: dict  # serialized AuthorityResult
    
    # Actions
    recommended_actions: list[str]
    
    # Draft document
    draft_document: Optional[str]
    draft_requested: bool
    
    # Final response
    final_response: dict
    translated_response: Optional[dict]
    
    # Pipeline control
    pipeline_error: Optional[str]
    debug_info: dict
