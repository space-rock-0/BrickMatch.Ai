from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ingestion_module_exists() -> None:
    """Phase 1 keeps the ingestion implementation in the application package."""
    module_path = ROOT / "app" / "data" / "ingest.py"
    assert module_path.is_file(), f"Missing ingestion module: {module_path}"


def test_ingestion_documentation_exists() -> None:
    """The repeatable local ingestion workflow is documented for reviewers."""
    documentation = ROOT / "docs" / "data_pipeline.md"
    assert documentation.is_file(), f"Missing ingestion docs: {documentation}"
