'''
what the file does?
This module implements the identify_entities graph node, which extracts structured domain entities (customer IDs/names, product SKUs, quantities, monetary values, dates) from user requests using LLM-driven JSON extraction.

Classes:
    None (LangGraph node module)

Methods:
    _get_llm: Instantiates the LLM client with zero temperature for structured JSON entity extraction.
    identify_entities: LangGraph node extracting entity key-values from user input into state['entities'].
'''

import json
import re

from langchain_groq import ChatGroq

from agents.graph.state import AgentState
from agents.prompts.prompts import ENTITY_EXTRACTION_PROMPT
from agents.llm import get_llm


def _get_llm() -> ChatGroq:
    return get_llm(temperature=0)


def identify_entities(state: AgentState) -> dict:
    """Extract structured business entities from the user's request.

    Uses the LLM to parse: customer name, product SKUs/names, quantities,
    discount %, invoice/order/quote IDs, amounts, and dates.

    Returns an empty dict if extraction fails — downstream nodes handle missing entities.
    """
    user_input = state["user_input"]

    if not user_input:
        return {"entities": {}}

    llm = _get_llm()
    prompt = ENTITY_EXTRACTION_PROMPT.format(user_input=user_input)

    try:
        response = llm.invoke(prompt)
        raw = response.content.strip()

        # Extract JSON from the response (handle markdown code blocks)
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            entities = json.loads(json_match.group())
            # Remove null values so downstream nodes can do simple `if "key" in entities`
            entities = {k: v for k, v in entities.items() if v is not None}
        else:
            entities = {}

        return {"entities": entities}

    except Exception as e:
        # Non-fatal — the workflow nodes will ask for clarification if they
        # need an entity that's missing
        return {"entities": {}, "error": f"Entity extraction warning: {e}"}
