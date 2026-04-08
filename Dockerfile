# ---- Stage 1: Build ----
FROM python:3.12-slim AS builder

WORKDIR /app
COPY pyproject.toml .
COPY src/ ./src/
RUN pip install --no-cache-dir .

# ---- Stage 2: Runtime ----
FROM python:3.12-slim AS runtime

# System deps for PDF/OCR extraction
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY src/ ./src/
COPY config.yaml ./

# Pre-download the default embedding model so first run is fast
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Volume mount points
VOLUME ["/data/books", "/data/db", "/data/manifest"]

ENV PYTHONPATH=/app/src
ENV BOOKS_PATH=/data/books
ENV CHROMA_PATH=/data/db
ENV MANIFEST_PATH=/data/manifest/.manifest.json

# Default: run MCP server over stdio
ENTRYPOINT ["python", "-m", "library_mcp.server"]
