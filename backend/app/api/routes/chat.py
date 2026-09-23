'''
This module defines the API routes for user interactions with the AI operations agent. It provides the primary natural-language endpoint where users send prompts or operational requests to be processed by the LangGraph agent state machine.
Classes:
    None (FastAPI router module).
Methods:
    post_chat: POST endpoint that takes a user message, executes the LangGraph agent workflow via run_agent, and returns the agent's response, detected intent, extracted entities, and any pending approval state.
'''

from fastapi import APIRouter, Depends, HTTPException
from backend.app.schemas.chat import ChatRequest, ChatResponse
from backend.app.api.dependencies import get_current_user
from agents.agent_service import run_agent

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse)
def post_chat(
    req: ChatRequest,
    current_user: dict = Depends(get_current_user),
) -> ChatResponse:
    """Send a prompt or operational request to the operations agent."""
    try:
        result = run_agent(
            user_input=req.message, conversation_id=req.conversation_id or req.thread_id,
            thread_id=req.thread_id, conversation_history=req.conversation_history or [])
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ChatResponse(
        response=result.get("response", ""),
        workflow=result.get("workflow"),
        intent=result.get("intent"),
        entities=result.get("entities", {}),
        approval_required=result.get("approval_required", False),
        approval_id=result.get("approval_id"),
        approval_decision=result.get("approval_decision"),
        thread_id=result.get("thread_id"),
        request_id=result.get("request_id"),
        error=result.get("error"),
    )
