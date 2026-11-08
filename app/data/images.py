"""Download explicitly permitted source images, sequentially and resumably."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from PIL import Image

from app.data.ingest import allowed_url, atomic_json

MAX_BYTES = 10 * 1024 * 1024


def download_images(manifest_path: Path, permission_confirmed: bool, limit: int = 10) -> dict:
    if not permission_confirmed:
        raise ValueError("Confirm permission to download source images before continuing")
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    image_dir = manifest_path.parent / "images"
    image_dir.mkdir(exist_ok=True)
    attempted = 0
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        for item in manifest:
            if attempted >= limit:
                break
            url = item["source_url"]
            if not url:
                continue
            if item["status"] == "downloaded" and item.get("path"):
                existing = image_dir / Path(item["path"]).name
                if existing.exists() and hashlib.sha256(existing.read_bytes()).hexdigest() == item["sha256"]:
                    continue
            if not allowed_url(url):
                item["status"] = "invalid"
                atomic_json(manifest_path, manifest)
                continue
            attempted += 1
            for attempt in range(3):
                try:
                    with client.stream("GET", url) as response:
                        if response.status_code == 404:
                            item["status"] = "missing"
                            break
                        response.raise_for_status()
                        content = bytearray()
                        for chunk in response.iter_bytes():
                            content.extend(chunk)
                            if len(content) > MAX_BYTES:
                                raise ValueError("image_exceeds_10mb")
                    with Image.open(io.BytesIO(content)) as image:
                        if image.width * image.height > 25_000_000:
                            raise ValueError("image_dimensions_exceed_limit")
                        image.verify()
                    digest = hashlib.sha256(content).hexdigest()
                    destination = image_dir / f"{digest}.img"
                    temporary = destination.with_suffix(".tmp")
                    temporary.write_bytes(content)
                    temporary.replace(destination)
                    item.update(status="downloaded", path=f"images/{destination.name}", sha256=digest,
                                retrieved_at=datetime.now(timezone.utc).isoformat())
                    item.pop("error", None)
                    break
                except (httpx.HTTPError, OSError, ValueError) as exc:
                    item.update(status="failed", error=type(exc).__name__)
                    transient = isinstance(exc, httpx.TransportError) or (
                        isinstance(exc, httpx.HTTPStatusError) and
                        (exc.response.status_code == 429 or exc.response.status_code >= 500))
                    if not transient or attempt == 2:
                        break
                    time.sleep(2 ** attempt)
            atomic_json(manifest_path, manifest)
    hashes = [item["sha256"] for item in manifest if item.get("sha256")]
    return {"attempted": attempted, "downloaded": sum(x["status"] == "downloaded" for x in manifest),
            "duplicate_image_hashes": len(hashes) - len(set(hashes))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--permission-confirmed", action="store_true")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    print(json.dumps(download_images(args.manifest, args.permission_confirmed, args.limit)))


if __name__ == "__main__":
    main()
