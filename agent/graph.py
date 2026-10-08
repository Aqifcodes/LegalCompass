"""
LegalCompass — LangGraph Pipeline

Graph:
  input_processor → language_service → intent_analyzer → context_manager
    → [interrupt if needs_context]
    → legal_retriever → evidence_selector → legal_reasoner
    → authority_mapper → action_recommender → document_drafter
    → response_builder → END
"""
from __future__ import annotations
from typing import Literal
from langgraph.graph import StateGraph, END

from agent.state import LegalCompassState
from agent.nodes.input_processor import input_processor
from agent.nodes.language_service import language_service
from agent.nodes.intent_analyzer import analyze_intent
from agent.nodes.context_manager import context_manager
from agent.nodes.legal_retriever import legal_retriever
from agent.nodes.evidence_selector import evidence_selector
from agent.nodes.legal_reasoner import legal_reasoner
from agent.nodes.authority_mapper import authority_mapper
from agent.nodes.action_recommender import action_recommender
from agent.nodes.document_drafter import document_drafter
from agent.nodes.response_builder import response_builder


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def route_context(state: LegalCompassState) -> Literal["ask_context", "retrieve"]:
    """After context_manager: pause if questions needed, else continue."""
    if state.get("needs_context", False):
        return "ask_context"
    return "retrieve"


def route_error(state: LegalCompassState) -> Literal["continue", "error_end"]:
    if state.get("pipeline_error"):
        return "error_end"
    return "continue"


# ---------------------------------------------------------------------------
# Error terminal node
# ---------------------------------------------------------------------------

def error_terminal(state: LegalCompassState) -> LegalCompassState:
    error_msg = state.get("pipeline_error", "An unknown error occurred.")
    state["final_response"] = {
        "case_summary": "",
        "law": {"plain_language_summary": "", "provisions": []},
        "application": "",
        "uncertainties": [],
        "next_steps": [],
        "authority": {},
        "draft_document": None,
        "sources": [],
        "disclaimer": "",
        "error": error_msg,
    }
    return state


# ---------------------------------------------------------------------------
# Context interrupt node — returns state with needs_context=True
# The API layer catches this and returns questions to the user.
# On resume, the user's answers are merged and the graph continues from
# legal_retriever.
# ---------------------------------------------------------------------------

def context_interrupt(state: LegalCompassState) -> LegalCompassState:
    """Terminal node when context questions need to be asked."""
    state["final_response"] = {
        "needs_context": True,
        "context_questions": state.get("context_questions", []),
        "case_summary": state.get("case_analysis", {}).get("case_summary", ""),
    }
    return state


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    builder = StateGraph(LegalCompassState)

    # Add nodes
    builder.add_node("input_processor", input_processor)
    builder.add_node("language_service", language_service)
    builder.add_node("intent_analyzer", analyze_intent)
    builder.add_node("context_manager", context_manager)
    builder.add_node("context_interrupt", context_interrupt)
    builder.add_node("error_terminal", error_terminal)
    builder.add_node("legal_retriever", legal_retriever)
    builder.add_node("evidence_selector", evidence_selector)
    builder.add_node("legal_reasoner", legal_reasoner)
    builder.add_node("authority_mapper", authority_mapper)
    builder.add_node("action_recommender", action_recommender)
    builder.add_node("document_drafter", document_drafter)
    builder.add_node("response_builder", response_builder)

    # Entry point
    builder.set_entry_point("input_processor")

    # Linear flow: input → language → intent
    builder.add_conditional_edges(
        "input_processor",
        route_error,
        {"continue": "language_service", "error_end": "error_terminal"},
    )
    builder.add_edge("language_service", "intent_analyzer")
    builder.add_edge("intent_analyzer", "context_manager")

    # Context branch
    builder.add_conditional_edges(
        "context_manager",
        route_context,
        {"ask_context": "context_interrupt", "retrieve": "legal_retriever"},
    )

    # Context interrupt ends (API layer resumes from legal_retriever on next call)
    builder.add_edge("context_interrupt", END)
    builder.add_edge("error_terminal", END)

    # Main pipeline
    builder.add_edge("legal_retriever", "evidence_selector")
    builder.add_edge("evidence_selector", "legal_reasoner")
    builder.add_edge("legal_reasoner", "authority_mapper")
    builder.add_edge("authority_mapper", "action_recommender")
    builder.add_edge("action_recommender", "document_drafter")
    builder.add_edge("document_drafter", "response_builder")
    builder.add_edge("response_builder", END)

    return builder.compile()


# ---------------------------------------------------------------------------
# Resume graph (called when user has answered context questions)
# ---------------------------------------------------------------------------

def build_resume_graph() -> StateGraph:
    """
    Graph for when context questions have been answered.
    Skips input_processor → context_manager and resumes from legal_retriever.
    """
    builder = StateGraph(LegalCompassState)

    builder.add_node("context_manager", context_manager)
    builder.add_node("legal_retriever", legal_retriever)
    builder.add_node("evidence_selector", evidence_selector)
    builder.add_node("legal_reasoner", legal_reasoner)
    builder.add_node("authority_mapper", authority_mapper)
    builder.add_node("action_recommender", action_recommender)
    builder.add_node("document_drafter", document_drafter)
    builder.add_node("response_builder", response_builder)

    builder.set_entry_point("context_manager")

    builder.add_conditional_edges(
        "context_manager",
        route_context,
        {"ask_context": "legal_retriever", "retrieve": "legal_retriever"},  # always continue
    )
    builder.add_edge("legal_retriever", "evidence_selector")
    builder.add_edge("evidence_selector", "legal_reasoner")
    builder.add_edge("legal_reasoner", "authority_mapper")
    builder.add_edge("authority_mapper", "action_recommender")
    builder.add_edge("action_recommender", "document_drafter")
    builder.add_edge("document_drafter", "response_builder")
    builder.add_edge("response_builder", END)

    return builder.compile()


# Compiled graph singletons
_graph = None
_resume_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def get_resume_graph():
    global _resume_graph
    if _resume_graph is None:
        _resume_graph = build_resume_graph()
    return _resume_graph


def run_pipeline(message: str, language: str = "auto", context_answers: dict = None, draft_requested: bool = False) -> dict:
    """
    Main entry point for the LegalCompass pipeline.
    Returns the final_response dict.
    """
    graph = get_graph()
    initial_state: LegalCompassState = {
        "original_input": message,
        "context_answers": context_answers or {},
        "draft_requested": draft_requested,
        "debug_info": {},
    }
    result = graph.invoke(initial_state)
    return result.get("final_response", {"error": "Pipeline produced no response"})


def run_with_context(original_input: str, case_analysis: dict, context_answers: dict, draft_requested: bool = False) -> dict:
    """
    Resume pipeline after user has answered context questions.
    """
    graph = get_resume_graph()
    state: LegalCompassState = {
        "original_input": original_input,
        "english_text": original_input,
        "case_analysis": case_analysis,
        "context_answers": context_answers,
        "draft_requested": draft_requested,
        "debug_info": {},
    }
    result = graph.invoke(state)
    return result.get("final_response", {"error": "Pipeline produced no response"})
