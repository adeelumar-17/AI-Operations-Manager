"""Compare the bundled ONNX vectors with the original SentenceTransformer.

Run export with the slim environment, then compare with the original environment.
Neither operation reads or writes your database.
"""
import argparse
import json
from pathlib import Path

TEXTS = [
    "What discount requires manager approval?",
    "Regular customers may receive a discount up to ten percent.",
    "Preferred customers may receive a discount up to fifteen percent.",
    "Refunds above $500 require management review.",
    "Payment reminders should use the unpaid invoice balance.",
    "Check stock before fulfilling an order.",
    "", "  Spaces and newlines\n\tare trimmed.  ",
    "OfficeHub café – customer account №42",
    "Long policy clause. " * 400,
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["export", "compare"])
    parser.add_argument("--file", default=".cache/onnx-parity.json")
    args = parser.parse_args()
    path = Path(args.file)
    if args.mode == "export":
        from rag.onnx_embeddings import embed, MODEL_ID, MODEL_REVISION
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"model": MODEL_ID, "revision": MODEL_REVISION,
                                    "texts": TEXTS, "vectors": [embed(text) for text in TEXTS]}), encoding="utf-8")
        print(f"Exported {len(TEXTS)} ONNX vectors without PyTorch.")
        return
    import numpy as np
    from sentence_transformers import SentenceTransformer
    data = json.loads(path.read_text(encoding="utf-8"))
    original = SentenceTransformer(data["model"], revision=data["revision"], device="cpu")
    reference = original.encode(data["texts"], convert_to_numpy=True)
    actual = np.asarray(data["vectors"], dtype=np.float32)
    if actual.shape != reference.shape or actual.shape[1] != 384:
        raise AssertionError("Embedding dimensions do not match.")
    np.testing.assert_allclose(actual, reference, rtol=2e-3, atol=2e-5)
    cosine = (actual * reference).sum(axis=1) / (np.linalg.norm(actual, axis=1) * np.linalg.norm(reference, axis=1))
    if cosine.min() < 0.99999:
        raise AssertionError("ONNX and original model embedding directions differ.")
    documents = slice(1, 6)
    if not np.array_equal(np.argsort(actual[documents] @ actual[0]), np.argsort(reference[documents] @ reference[0])):
        raise AssertionError("Policy ranking changed.")
    print(f"Parity passed for {len(actual)} texts; minimum cosine {cosine.min():.8f}; policy ranking unchanged.")


if __name__ == "__main__":
    main()
