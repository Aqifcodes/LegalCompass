"""
LegalCompass — Flask Routes

GET  /           → frontend index page
POST /api/analyze → main legal analysis endpoint
POST /api/context → resume pipeline after context answers
POST /api/draft   → generate draft document separately
GET  /api/status  → health check
"""
from __future__ import annotations
import os
import json
import traceback
from flask import Blueprint, request, jsonify, render_template, current_app

api_bp = Blueprint("api", __name__)

# Simple in-memory session store (per process)
# For production: use Redis or a proper session store
_sessions: dict[str, dict] = {}


@api_bp.route("/")
def index():
    return render_template("index.html")


@api_bp.route("/api/status")
def status():
    return jsonify({
        "status": "ok",
        "service": "LegalCompass",
        "version": "1.0.0",
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY")),
        "sarvam_configured": bool(os.getenv("SARVAM_API_KEY")),
    })


@api_bp.route("/api/analyze", methods=["POST"])
def analyze():
    """
    Main analysis endpoint.
    Input: {message, language?, session_id?, draft_requested?}
    Returns: {status, needs_context, context_questions?, result?}
    """
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"status": "error", "error": "No JSON body received"}), 400

        message = (data.get("message") or "").strip()
        if not message:
            return jsonify({"status": "error", "error": "Message is required"}), 400

        language = data.get("language", "auto")
        session_id = data.get("session_id")
        draft_requested = bool(data.get("draft_requested", False))

        # Import here to avoid startup errors if env not yet set
        from agent.graph import run_pipeline

        result = run_pipeline(
            message=message,
            language=language,
            context_answers={},
            draft_requested=draft_requested,
        )

        # Check if pipeline needs context
        if result.get("needs_context"):
            # Store case_analysis for resume
            if session_id:
                _sessions[session_id] = {
                    "original_input": message,
                    "case_analysis": result.get("case_analysis", {}),
                }
            return jsonify({
                "status": "needs_context",
                "needs_context": True,
                "context_questions": result.get("context_questions", []),
                "case_summary": result.get("case_summary", ""),
                "session_id": session_id,
            })

        return jsonify({
            "status": "success",
            "needs_context": False,
            "result": result,
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "error": f"Analysis failed: {str(e)}",
        }), 500


@api_bp.route("/api/context", methods=["POST"])
def provide_context():
    """
    Resume pipeline after user has answered context questions.
    Input: {session_id?, original_input, case_analysis?, context_answers, draft_requested?}
    """
    try:
        data = request.get_json(force=True)
        original_input = data.get("original_input", "")
        context_answers = data.get("context_answers", {})
        draft_requested = bool(data.get("draft_requested", False))
        session_id = data.get("session_id")

        # Try to recover case_analysis from session
        case_analysis = data.get("case_analysis") or {}
        if session_id and session_id in _sessions:
            stored = _sessions[session_id]
            if not case_analysis:
                case_analysis = stored.get("case_analysis", {})
            if not original_input:
                original_input = stored.get("original_input", "")

        if not original_input and not case_analysis:
            return jsonify({"status": "error", "error": "No original input or case analysis found"}), 400

        from agent.graph import run_with_context

        result = run_with_context(
            original_input=original_input,
            case_analysis=case_analysis,
            context_answers=context_answers,
            draft_requested=draft_requested,
        )

        return jsonify({
            "status": "success",
            "needs_context": False,
            "result": result,
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500


@api_bp.route("/api/draft", methods=["POST"])
def generate_draft():
    """
    Generate / regenerate a draft document.
    Input: {case_analysis, selected_evidence, authority, document_type}
    """
    try:
        data = request.get_json(force=True)
        case_analysis = data.get("case_analysis", {})
        selected_evidence = data.get("selected_evidence", [])
        authority = data.get("authority", {})
        doc_type = data.get("document_type", "salary_notice")

        from agent.services.drafting_templates import select_and_draft

        draft = select_and_draft(
            document_type=doc_type,
            case_analysis=case_analysis,
            selected_evidence=selected_evidence,
            authority=authority,
        )

        return jsonify({"status": "success", "draft": draft})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500
