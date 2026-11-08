FROM python:3.11-slim
WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --no-cache-dir .

COPY frontend ./frontend
COPY data/evaluation_results.json ./data/evaluation_results.json
COPY data/processed/78b8926d0b520375 ./data/processed/78b8926d0b520375
COPY artifacts/embeddings/clip.npz ./artifacts/embeddings/clip.npz
COPY artifacts/models ./artifacts/models

ENV BRICKMATCH_UI_DIR=/app/frontend/web \
    BRICKMATCH_EVALUATION=/app/data/evaluation_results.json \
    BRICKMATCH_CATALOG=/app/data/processed/78b8926d0b520375/catalog.json \
    BRICKMATCH_EMBEDDINGS=/app/artifacts/embeddings/clip.npz \
    BRICKMATCH_CLASSIFIER_DIR=/app/artifacts/models

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/live', timeout=3)"
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
