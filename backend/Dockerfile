FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.1 /uv /uvx /bin/
RUN apt-get update && apt-get install -y --no-install-recommends git libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./backend/
RUN cd backend && uv sync --frozen --no-dev
COPY scripts/fetch_facephys.py ./scripts/fetch_facephys.py
RUN python scripts/fetch_facephys.py
COPY backend/pulsepilot ./backend/pulsepilot
ENV PATH="/app/backend/.venv/bin:$PATH" \
    KERAS_BACKEND=jax \
    XLA_PYTHON_CLIENT_PREALLOCATE=false \
    FACEPHYS_ROOT=/app/.vendor/open-rppg
WORKDIR /app/backend
EXPOSE 8000
CMD ["uvicorn", "pulsepilot.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--ws-max-size", "1500008"]
