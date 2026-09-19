'''
what the file does?
This module implements the classify_intent graph node, which uses an LLM call (with keyword fallback) to categorize user requests into one of the six supported business workflows.

Classes:
    None (LangGraph node module)

Methods:
    _get_llm: Instantiates the LLM client configured with zero temperature for deterministic classification.
    classify_intent: LangGraph node that analyzes user input and updates the state with the classified intent.
    _keyword_fallback: Rule-based heuristic fallback to classify intent based on keywords when LLM fails.
'''

import re

from langchain_groq import ChatGroq

from agents.graph.state import AgentState, ALL_WORKFLOWS
from agents.prompts.prompts import INTENT_CLASSIFICATION_PROMPT, SYSTEM_PROMPT
from agents.llm import get_llm


def _get_llm() -> ChatGroq:
    return get_llm(temperature=0)


def classify_intent(state: AgentState) -> dict:
    """Use the LLM to classify the user's intent into one of 6 workflow names.

    Falls back to 'customer_management' if the LLM returns something unexpected,
    so the graph always has a valid routing target.
    """
    user_input = state["user_input"]

    if not user_input:
        return {"intent": "customer_management", "error": "Empty user input"}

    llm = _get_llm()
    prompt = INTENT_CLASSIFICATION_PROMPT.format(user_input=user_input)

    try:
        response = llm.invoke(prompt)
        raw_intent = response.content.strip().lower()

        # Extract the workflow name from the response (handles extra text gracefully)
        detected_intent = None
        for workflow in ALL_WORKFLOWS:
            if workflow in raw_intent:
                detected_intent = workflow
                break

        if detected_intent is None:
            # Fallback: pick the most mentioned workflow keyword from the user input
            detected_intent = _keyword_fallback(user_input)

        return {"intent": detected_intent}

    except Exception as e:
        return {
            "intent": _keyword_fallback(user_input),
            "error": f"Intent classification error (using keyword fallback): {e}",
        }


def _keyword_fallback(user_input: str) -> str:
    """Simple keyword-based fallback when LLM classification fails."""
    text = user_input.lower()

    if any(w in text for w in ["stock", "inventory", "fulfil", "available", "units", "restock"]):
        return "inventory_check"
    if any(w in text for w in ["quote", "discount", "price", "pricing"]):
        return "create_quote"
    if any(w in text for w in ["invoice", "payment", "overdue", "paid", "bill"]):
        return "invoice_status"
    if any(w in text for w in ["complaint", "issue", "problem", "return", "refund", "wrong"]):
        return "issue_resolution"
    if any(w in text for w in ["follow", "remind", "check in", "follow-up"]):
        return "follow_up"
    return "customer_management"
