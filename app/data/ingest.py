"""Repeatable local Rebrickable CSV ingestion with content-addressed outputs."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def rows(path: Path, required: set[str] | None = None):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if required and not required.issubset(reader.fieldnames or []):
            raise ValueError(f"Missing required CSV columns: {sorted(required - set(reader.fieldnames or []))}")
        yield from reader


def allowed_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        return (parsed.scheme == "https" and parsed.hostname in {
            "cdn.rebrickable.com", "rebrickable.com"
        } and parsed.username is None and parsed.password is None
                and parsed.port in (None, 443))
    except ValueError:
        return False


def ingest(sets_file: Path, themes_file: Path, output: Path, limit: int = 500) -> dict:
    if not 1 <= limit <= 10000:
        raise ValueError("limit must be between 1 and 10000")
    theme_names = {}
    for row in rows(themes_file, {"id", "name"}):
        theme_id = int(row["id"])
        if theme_id in theme_names or not row["name"].strip():
            raise ValueError("Duplicate theme ID or empty theme name")
        theme_names[theme_id] = row["name"].strip()
    records, rejected, seen = [], [], set()
    total = 0
    for number, row in enumerate(rows(sets_file, {"set_num", "name", "year", "theme_id", "num_parts"}), 2):
        total += 1
        try:
            set_id = row["set_num"].strip()
            if not set_id or len(set_id) > 80:
                raise ValueError("invalid_set_id")
            if set_id in seen:
                raise ValueError("duplicate_set_id")
            name = row["name"].strip()
            year, theme_id, parts = int(row["year"]), int(row["theme_id"]), int(row["num_parts"])
            if not name or not 1949 <= year <= datetime.now(UTC).year + 2:
                raise ValueError("invalid_name_or_year")
            if not 0 <= parts <= 100000 or theme_id not in theme_names:
                raise ValueError("invalid_parts_or_theme")
            image = (row.get("img_url") or "").strip()
            if image and not allowed_url(image):
                raise ValueError("invalid_image_url")
            seen.add(set_id)
            records.append({"set_id": set_id, "name": name, "year": year,
                            "theme_id": theme_id, "theme": theme_names[theme_id],
                            "num_parts": parts, "image_url": image or None,
                            "source": "rebrickable_local_csv"})
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            rejected.append({"line": number, "reason": str(exc)})
    records.sort(key=lambda item: item["set_id"])
    selected = records[:limit]
    digests = {"sets_sha256": hashlib.sha256(sets_file.read_bytes()).hexdigest(),
               "themes_sha256": hashlib.sha256(themes_file.read_bytes()).hexdigest()}
    version = hashlib.sha256(json.dumps({**digests, "limit": limit, "schema": 1},
                                       sort_keys=True).encode()).hexdigest()[:16]
    folder = output / version
    manifest_path = folder / "image_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else []
    previous = {item["set_id"]: item for item in manifest}
    images = []
    for item in selected:
        old = previous.get(item["set_id"])
        images.append(old if old and old["source_url"] == item["image_url"] else {
            "set_id": item["set_id"], "source_url": item["image_url"],
            "status": "pending" if item["image_url"] else "missing",
            "path": None, "sha256": None, "retrieved_at": None})
    report = {"dataset_version": version, "source_rows": total,
              "valid_rows": len(records), "selected_rows": len(selected),
              "rejected_rows": len(rejected), "rejections": rejected,
              "missing_images": sum(not item["image_url"] for item in selected),
              "source_hashes": digests, "schema_version": 1}
    atomic_json(folder / "catalog.json", selected)
    atomic_json(manifest_path, images)
    atomic_json(folder / "quality_report.json", report)
    return {**report, "output_directory": str(folder)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sets", type=Path, required=True)
    parser.add_argument("--themes", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("data/processed"))
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()
    print(json.dumps(ingest(args.sets, args.themes, args.output, args.limit), indent=2))


if __name__ == "__main__":
    main()
