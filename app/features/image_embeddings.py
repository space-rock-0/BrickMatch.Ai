"""Generate one-image CPU CLIP embeddings with content-addressed resume caches."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np

from app.features.artifacts import cache_key, load_bundle, save_bundle


def generate(manifest_path: Path, output: Path, model_id: str, revision: str):
    # Revision must be a commit hash: floating tags would invalidate resume guarantees.
    if len(revision) != 40 or any(char not in "0123456789abcdef" for char in revision.lower()):
        raise ValueError("Supply the pinned 40-character model commit revision")
    os.environ.setdefault("HF_HOME", str(Path(".cache/huggingface").resolve()))
    import torch
    from PIL import Image
    from transformers import CLIPModel, CLIPProcessor

    entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    if len({item["set_id"] for item in entries}) != len(entries):
        raise ValueError("Duplicate manifest set IDs")
    start = time.perf_counter()
    model = processor = None
    ids, vectors, failures = [], [], []
    reused = 0
    root = manifest_path.parent.resolve()
    cache = output.parent / "cache"
    for item in sorted(entries, key=lambda row: row["set_id"]):
        if item["status"] != "downloaded":
            failures.append({"set_id": item["set_id"], "reason": "image_unavailable"})
            continue
        try:
            image_path = (root / item["path"]).resolve()
            if not image_path.is_relative_to(root):
                raise ValueError("image_path_outside_dataset")
            image_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()
            if image_hash != item["sha256"]:
                raise ValueError("image_checksum_mismatch")
            cached = cache / (cache_key(image_hash, model_id, revision) + ".npz")
            vector = None
            if cached.exists():
                try:
                    _, prior, _ = load_bundle(cached)
                    if prior.shape[0] != 1:
                        raise ValueError("Invalid cache shape")
                    vector = prior[0]
                    reused += 1
                except (ValueError, OSError, KeyError):
                    vector = None
            if vector is None:
                if model is None:
                    torch.set_num_threads(2)
                    model = CLIPModel.from_pretrained(model_id, revision=revision).cpu().eval()
                    processor = CLIPProcessor.from_pretrained(model_id, revision=revision)
                with Image.open(image_path) as image:
                    inputs = processor(images=image.convert("RGB"), return_tensors="pt")
                with torch.inference_mode():
                    vector = model.get_image_features(**inputs).numpy()[0].astype(np.float32)
                norm = np.linalg.norm(vector)
                if not np.isfinite(norm) or norm <= 0:
                    raise ValueError("invalid_encoder_output")
                vector /= norm
                save_bundle(cached, [image_hash], vector[None, :],
                            {"model": model_id, "revision": revision, "image_hash": image_hash})
            ids.append(item["set_id"])
            vectors.append(vector)
        except (OSError, ValueError, KeyError) as exc:
            failures.append({"set_id": item["set_id"], "reason": str(exc)})
    if not vectors:
        raise ValueError("No valid images: no embedding artifact was published")
    metadata = {"model": model_id, "revision": revision, "processor_version": "clip-processor-v1",
                "source_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                "failures": failures, "reused": reused,
                "elapsed_seconds": time.perf_counter() - start}
    save_bundle(output, ids, np.stack(vectors), metadata)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/embeddings/clip.npz"))
    parser.add_argument("--model", default="openai/clip-vit-base-patch32")
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    print(json.dumps(generate(args.manifest, args.output, args.model, args.revision), indent=2))


if __name__ == "__main__":
    main()
