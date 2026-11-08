"""Run actual CPU CLIP and retrieval checks; save machine-readable evidence."""
import json
import os
import platform
import shutil
import time
from pathlib import Path

os.environ.setdefault("HF_HOME", str(Path(".cache/huggingface").resolve()))


def main():
    import numpy as np
    import torch
    from PIL import Image
    from sklearn.neighbors import NearestNeighbors
    from transformers import CLIPModel, CLIPProcessor

    model_id = "openai/clip-vit-base-patch32"
    torch.set_num_threads(2)
    model = CLIPModel.from_pretrained(model_id).cpu().eval()
    processor = CLIPProcessor.from_pretrained(model_id)
    # Generated solid-color fixture checks the encoder, not recommendation quality.
    inputs = processor(images=Image.new("RGB", (224, 224), "red"), return_tensors="pt")
    start = time.perf_counter()
    with torch.inference_mode():
        vector = model.get_image_features(**inputs).numpy()
    elapsed = time.perf_counter() - start
    assert vector.ndim == 2 and vector.shape[0] == 1
    assert np.isfinite(vector).all() and np.linalg.norm(vector) > 0
    vector = vector / np.linalg.norm(vector, axis=1, keepdims=True)
    neighbors = NearestNeighbors(metric="cosine").fit(vector)
    assert neighbors.kneighbors(vector, n_neighbors=1)[1].tolist() == [[0]]
    report = {"platform": platform.platform(), "python": platform.python_version(),
              "cpu": platform.processor(), "logical_cpus": os.cpu_count(),
              "free_disk_gib": round(shutil.disk_usage('.').free / 2**30, 2),
              "torch": torch.__version__, "device": "cpu", "model": model_id,
              "model_revision": model.config._commit_hash, "shape": list(vector.shape),
              "finite": True, "inference_seconds": elapsed, "sklearn_retrieval": "passed"}
    try:
        import faiss
        index = faiss.IndexFlatIP(vector.shape[1])
        index.add(vector)
        assert index.search(vector, 1)[1].tolist() == [[0]]
        report["faiss_retrieval"] = "passed"
    except ImportError as exc:
        report["faiss_retrieval"] = f"unavailable: {exc}"
    Path("docs").mkdir(exist_ok=True)
    Path("docs/preflight_result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
