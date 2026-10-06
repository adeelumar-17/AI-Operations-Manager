"""The same MiniLM transformer, pooling and normalization without PyTorch."""
import os
from pathlib import Path
from threading import Lock
import numpy as np

MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
MODEL_FILES = ("onnx/model.onnx", "tokenizer.json")
DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "minilm"
_model = None
_load_lock = Lock()


def download_model(destination: Path) -> None:
    """Download only pinned inference assets, never the PyTorch model."""
    import shutil
    from huggingface_hub import hf_hub_download
    destination.mkdir(parents=True, exist_ok=True)
    for name in MODEL_FILES:
        cached = hf_hub_download(MODEL_ID, name, revision=MODEL_REVISION)
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(cached, target)


class MiniLM:
    def __init__(self, directory: Path):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self.session = ort.InferenceSession(str(directory / "onnx/model.onnx"), options,
                                           providers=["CPUExecutionProvider"])
        self.tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=256)
        self.inputs = {item.name for item in self.session.get_inputs()}

    def encode(self, text: str) -> list[float]:
        # SentenceTransformer's Transformer tokenizer strips surrounding whitespace.
        tokens = self.tokenizer.encode(text.strip())
        mask = np.asarray([tokens.attention_mask], dtype=np.int64)
        inputs = {"input_ids": np.asarray([tokens.ids], dtype=np.int64),
                  "attention_mask": mask,
                  "token_type_ids": np.asarray([tokens.type_ids], dtype=np.int64)}
        hidden = self.session.run(None, {name: value for name, value in inputs.items() if name in self.inputs})[0]
        weights = mask[:, :, None].astype(np.float32)
        pooled = (hidden * weights).sum(axis=1) / np.clip(weights.sum(axis=1), 1e-9, None)
        vector = pooled[0]
        vector = vector / max(float(np.linalg.norm(vector)), 1e-12)
        if vector.shape != (384,) or not np.isfinite(vector).all():
            raise ValueError("MiniLM must return 384 finite embedding values.")
        return vector.tolist()


def get_model() -> MiniLM:
    global _model
    if _model is None:
        with _load_lock:
            if _model is None:
                configured = os.getenv("SENTENCE_TRANSFORMERS_MODEL", "all-MiniLM-L6-v2")
                if configured not in ("all-MiniLM-L6-v2", MODEL_ID):
                    raise ValueError("The ONNX backend supports all-MiniLM-L6-v2 only; keep the matching model for existing policy vectors.")
                directory = Path(os.getenv("ONNX_MODEL_DIR", str(DEFAULT_MODEL_DIR)))
                if not all((directory / name).is_file() for name in MODEL_FILES):
                    if os.getenv("VERCEL") == "1":
                        raise RuntimeError("Bundled ONNX assets are missing. Run the configured Vercel model build command.")
                    download_model(directory)
                _model = MiniLM(directory)
    return _model


def embed(text: str) -> list[float]:
    return get_model().encode(text)
