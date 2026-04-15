# ── Stage 1: build dependencies ───────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Non-root user for security
RUN addgroup --system ccl && adduser --system --ingroup ccl ccl

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy law bundles (offline data)
COPY laws/ /app/laws/

# Copy engine source
COPY src/ /app/src/
COPY pyproject.toml .

# Install the package itself (editable-like, no extra deps)
RUN pip install --no-cache-dir --no-deps -e .

ENV LAWS_DIR=/app/laws
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

USER ccl

ENTRYPOINT ["python", "-m", "ccl.cli"]
CMD ["--help"]
