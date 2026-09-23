import logging
logger = logging.getLogger(__name__)
'''
what the file does?
This module provides a LangChain-compatible RAG policy search tool for the operations agent, querying embedded business policy documents and procedures to guide operational decisions (discounts, refunds, approval rules).

Classes:
    None (LangChain tool definition module)

Methods:
    search_business_policy: Tool that performs semantic search over indexed policy documents using the RAG retriever.
'''

from typing import Annotated

from langchain_core.tools import tool


from rag.retriever import retrieve_with_session
from backend.app.db.database import SessionLocal


@tool
def search_business_policy(
    query: Annotated[
        str,
        "A natural language question about business rules, policies, or procedures. "
        "Examples: 'max discount for regular customers', 'what is the return window', "
        "'when is manager approval required for a refund'",
    ],
    top_k: Annotated[int, "Number of policy chunks to return (default 3)"] = 3,
) -> str:
    """Search OfficeHub policy documents for rules relevant to the current situation.

    Use this before applying discounts, processing refunds, or making any decision
    that might be governed by a business rule. Returns the most relevant policy
    sections ranked by semantic similarity.

    Examples of when to call this:
      - "What is the maximum discount I can offer?"
      - "Does this refund require approval?"
      - "What is the standard payment term?"
    """


    try:
        if not 1 <= top_k <= 20:
            raise ValueError("top_k must be between 1 and 20.")
        with SessionLocal() as session:
            results = retrieve_with_session(query, session, top_k=top_k)
        if not results:
            return "No relevant policy found for that query."

        lines = [f"Policy search results for: '{query}'\n"]
        for i, result in enumerate(results, 1):
            lines.append(f"[{i}] {result.document_title} (similarity: {result.similarity_score:.3f})")
            lines.append(f"    {result.content.strip()}")
            lines.append("")

        return "\n".join(lines)
    except Exception as e:
        logger.exception('Operation failed')
        return f"Error searching policy database: {e}"
