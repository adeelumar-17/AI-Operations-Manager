'''
what the file does?
This module provides central LLM configuration and client utilities for Groq, supporting ChatGroq instantiation for LangGraph nodes and direct streaming chat completions.

Classes:
    None (LLM factory and utility module)

Methods:
    get_groq_client: Initializes and returns a native Groq SDK client using configured API keys.
    get_llm: Instantiates and configures a ChatGroq client with model, temperature, token limits, and reasoning effort.
    stream_chat_completion: Generator streaming chat completion tokens via native Groq SDK client.
'''

import sys
from typing import Generator, Optional, Any
from groq import Groq
from langchain_groq import ChatGroq

from backend.app.core.config import settings


def get_groq_client() -> Groq:
    """Return an initialized native Groq client."""
    return Groq(api_key=settings.GROQ_API_KEY or None)


def get_llm(
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    reasoning_effort: Optional[str] = None,
    **kwargs: Any,
) -> ChatGroq:
    """Return a configured ChatGroq instance for LangGraph nodes.

    Defaults to settings (openai/gpt-oss-120b, temperature=1.0, max_tokens=2048, reasoning_effort="medium").
    """
    model_name = model or settings.GROQ_MODEL
    temp = settings.GROQ_TEMPERATURE if temperature is None else temperature
    tokens = max_tokens or settings.GROQ_MAX_TOKENS
    effort = reasoning_effort or settings.GROQ_REASONING_EFFORT

    groq_kwargs: dict[str, Any] = {
        "model": model_name,
        "temperature": temp,
        "max_tokens": tokens,
        "api_key": settings.GROQ_API_KEY or None,
    }

    # Pass reasoning_effort if specified
    if effort:
        groq_kwargs["reasoning_effort"] = effort

    groq_kwargs.update(kwargs)
    return ChatGroq(**groq_kwargs)


def stream_chat_completion(
    messages: list[dict],
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_completion_tokens: Optional[int] = None,
    top_p: float = 1.0,
    reasoning_effort: Optional[str] = None,
    stop: Optional[str] = None,
) -> Generator[str, None, None]:
    """Stream chat completion using the native Groq SDK client.

    Yields token content chunks as they arrive.
    """
    client = get_groq_client()
    completion = client.chat.completions.create(
        model=model or settings.GROQ_MODEL,
        messages=messages,
        temperature=settings.GROQ_TEMPERATURE if temperature is None else temperature,
        max_completion_tokens=max_completion_tokens or settings.GROQ_MAX_TOKENS,
        top_p=top_p,
        reasoning_effort=reasoning_effort or settings.GROQ_REASONING_EFFORT,
        stream=True,
        stop=stop,
    )

    for chunk in completion:
        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


if __name__ == "__main__":
    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Hello! Introduce yourself in two sentences."
    print(f"Streaming from model '{settings.GROQ_MODEL}':\n")
    for chunk in stream_chat_completion([{"role": "user", "content": prompt}]):
        print(chunk, end="", flush=True)
    print("\n")
