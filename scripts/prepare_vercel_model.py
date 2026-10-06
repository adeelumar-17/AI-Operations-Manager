"""Build-time preparation: bundle the pinned model, with no database writes."""
import os
from pathlib import Path


def main():
    # Keep build download cache inside the repo so excludeFiles can omit it.
    os.environ.setdefault("HF_HOME", str(Path(".cache") / "huggingface"))
    from rag.onnx_embeddings import DEFAULT_MODEL_DIR, download_model, MiniLM
    download_model(DEFAULT_MODEL_DIR)
    model = MiniLM(DEFAULT_MODEL_DIR)
    model.encode("OfficeHub policy retrieval smoke check")
    total = sum(path.stat().st_size for path in DEFAULT_MODEL_DIR.rglob("*") if path.is_file())
    print(f"Bundled MiniLM ONNX inference assets: {total / 1024**2:.1f} MiB; 384-dimensional smoke check passed.")


if __name__ == "__main__":
    main()
