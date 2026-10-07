"""
LegalCompass — Authority Service

Deterministic authority matching based on:
- employer type (central/state)
- location (state)
- issue type (PF → EPFO, wages → Labour Commissioner)
- keywords in employer description

Gemini NEVER touches authority selection.
"""

from __future__ import annotations
import json
import urllib.parse
from pathlib import Path
from typing import Optional

AUTHORITIES_PATH = Path(__file__).parent.parent.parent / "data/authorities/labour_authorities.json"

_authorities_data: Optional[dict] = None


def _load() -> dict:
    global _authorities_data
    if _authorities_data is None:
        with open(AUTHORITIES_PATH) as f:
            _authorities_data = json.load(f)
    return _authorities_data


def _get_authority_by_id(authority_id: str) -> Optional[dict]:
    data = _load()
    for a in data["authorities"]:
        if a["authority_id"] == authority_id:
            return a
    return None


def _maps_url(maps_query: str) -> str:
    if not maps_query:
        return ""
    return f"https://maps.google.com/?q={urllib.parse.quote(maps_query)}"


def _build_result(
    authority: dict,
    reason: str,
    confidence: str,
    verification_note: Optional[str] = None,
    secondary: Optional[list[dict]] = None,
) -> dict:
    return {
        "authority_id": authority["authority_id"],
        "name": authority["name"],
        "short_name": authority["short_name"],
        "department": authority["department"],
        "level": authority["level"],
        "jurisdiction": authority["jurisdiction_description"],
        "address": authority["address"],
        "phone": authority.get("phone"),
        "official_website": authority.get("official_website"),
        "maps_url": _maps_url(authority.get("maps_query", "")),
        "reason_for_selection": reason,
        "confidence": confidence,
        "verification_note": verification_note,
        "secondary_authorities": secondary or [],
        "notes": authority.get("notes", ""),
    }


def map_authority(case_analysis: dict) -> dict:
    """
    Determine the most relevant labour authority from case facts.

    Priority:
    1. PF issues → EPFO
    2. Central sphere employer → Regional CLC / CLC(C)
    3. Known state → State Labour Commissioner
    4. Unknown → NEEDS_VERIFICATION
    """
    data = _load()
    issue_types = case_analysis.get("issue_type", [])
    employer_type = (case_analysis.get("employer_type") or "").lower()
    location_state = (case_analysis.get("location_state") or "").strip()
    location_city = (case_analysis.get("location_city") or "").strip()
    employer_name = (case_analysis.get("employer_name") or "").lower()
    central_keywords = data.get("central_sphere_keywords", [])

    nalsa = _get_authority_by_id("NALSA_GENERIC")
    nalsa_secondary = _build_result(
        nalsa,
        reason="Free legal aid is available from NALSA/SALSA for eligible workers",
        confidence="HIGH",
    ) if nalsa else {}

    # 1. PF / gratuity / maternity → EPFO (for PF specifically)
    if any(t in issue_types for t in ["provident_fund"]):
        epfo = _get_authority_by_id("EPFO_HO")
        if epfo:
            return _build_result(
                epfo,
                reason="Provident Fund matters are handled by EPFO. File a grievance at epfigms.gov.in or contact your regional EPFO office.",
                confidence="HIGH",
                secondary=[nalsa_secondary] if nalsa_secondary else [],
            )

    # 2. Check if employer is in central sphere
    is_central = False
    central_reason = ""
    if employer_type in ("central government", "central_psu", "railways", "bank", "banking", "insurance", "mine", "mines"):
        is_central = True
        central_reason = f"Employer type '{employer_type}' falls under central sphere jurisdiction"
    else:
        for kw in central_keywords:
            if kw in employer_name:
                is_central = True
                central_reason = f"Employer name contains '{kw}', indicating possible central sphere establishment"
                break

    if is_central:
        # Try to find regional CLC
        if location_state in ("Telangana", "Andhra Pradesh"):
            rlc = _get_authority_by_id("REGIONAL_CLC_HYDERABAD")
            if rlc:
                return _build_result(
                    rlc,
                    reason=f"Central sphere establishment in Telangana/AP. {central_reason}",
                    confidence="HIGH",
                    verification_note="Verify that this establishment is covered under central sphere before approaching.",
                    secondary=[nalsa_secondary] if nalsa_secondary else [],
                )
        # Default to CLC central
        clc = _get_authority_by_id("CLC_CENTRAL")
        if clc:
            return _build_result(
                clc,
                reason=f"Central sphere establishment. {central_reason}",
                confidence="MEDIUM",
                verification_note="Verify central sphere classification. Contact nearest Regional Labour Commissioner (Central) office.",
                secondary=[nalsa_secondary] if nalsa_secondary else [],
            )

    # 3. State-based matching
    state_to_auth = data.get("state_to_authority_id", {})
    if location_state and location_state in state_to_auth:
        auth_id = state_to_auth[location_state]
        authority = _get_authority_by_id(auth_id)
        if authority:
            return _build_result(
                authority,
                reason=f"Private establishment in {location_state}. State Labour Commissioner handles employment matters for state-jurisdiction establishments.",
                confidence="MEDIUM",
                verification_note="Verify that this establishment is under state jurisdiction and not under a central sphere industry.",
                secondary=[nalsa_secondary] if nalsa_secondary else [],
            )

    # 4. City-based fallback
    if location_city:
        city_lower = location_city.lower()
        if any(c in city_lower for c in ["hyderabad", "secunderabad", "warangal"]):
            auth = _get_authority_by_id("STATE_LC_TELANGANA")
            if auth:
                return _build_result(
                    auth,
                    reason=f"Location identified as {location_city} (Telangana). State Labour Commissioner may be the appropriate authority for state-sphere establishments.",
                    confidence="MEDIUM",
                    verification_note="Verify jurisdiction. If the employer is in a central sphere industry, approach the Regional Labour Commissioner (Central) instead.",
                    secondary=[nalsa_secondary] if nalsa_secondary else [],
                )
        if any(c in city_lower for c in ["bangalore", "bengaluru", "mysore", "hubli"]):
            auth = _get_authority_by_id("STATE_LC_KARNATAKA")
            if auth:
                return _build_result(
                    auth,
                    reason=f"Location identified as {location_city} (Karnataka).",
                    confidence="MEDIUM",
                    verification_note="Verify jurisdiction before approaching.",
                )
        if any(c in city_lower for c in ["mumbai", "pune", "nagpur", "thane"]):
            auth = _get_authority_by_id("STATE_LC_MAHARASHTRA")
            if auth:
                return _build_result(
                    auth,
                    reason=f"Location identified as {location_city} (Maharashtra).",
                    confidence="MEDIUM",
                    verification_note="Verify jurisdiction before approaching.",
                )
        if any(c in city_lower for c in ["chennai", "coimbatore", "madurai"]):
            auth = _get_authority_by_id("STATE_LC_TAMIL_NADU")
            if auth:
                return _build_result(
                    auth,
                    reason=f"Location identified as {location_city} (Tamil Nadu).",
                    confidence="MEDIUM",
                    verification_note="Verify jurisdiction before approaching.",
                )
        if any(c in city_lower for c in ["delhi", "new delhi", "gurgaon", "noida"]):
            auth = _get_authority_by_id("STATE_LC_DELHI")
            if auth:
                return _build_result(
                    auth,
                    reason=f"Location identified as {location_city} (Delhi).",
                    confidence="MEDIUM",
                    verification_note="If employer is in central sphere (bank, railway, etc.), approach CLC(C) instead.",
                )

    # 5. Fallback — cannot determine
    clc = _get_authority_by_id("CLC_CENTRAL")
    return _build_result(
        clc or _load()["authorities"][0],
        reason="Authority could not be determined from available facts. The appropriate authority depends on the employer's industry, state, and whether it falls under central or state jurisdiction.",
        confidence="NEEDS_VERIFICATION",
        verification_note="Please provide: (1) the state where you work, (2) the type of employer (private company, government, bank, railway, etc.) so the correct authority can be identified.",
        secondary=[nalsa_secondary] if nalsa_secondary else [],
    )
