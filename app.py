"""Vercel's Python entrypoint; exports the existing FastAPI application."""
import os

if os.getenv("VERCEL") == "1":
    os.environ.setdefault("EMBEDDING_BACKEND", "onnx")
    if os.environ["EMBEDDING_BACKEND"] != "onnx":
        raise RuntimeError("Set EMBEDDING_BACKEND=onnx for the lightweight Vercel dependency profile.")

from backend.app.main import app  # noqa: E402,F401
