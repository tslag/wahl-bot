FROM python:3.11-slim AS builder

# Reduce layer size and ensure predictable behavior
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install build-time dependencies and build wheels for all requirements
COPY requirements.txt ./
RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip wheel --no-deps --wheel-dir /wheels -r requirements.txt

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Runtime OS deps (smallest set needed to run compiled packages)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN useradd --create-home --shell /usr/sbin/nologin appuser

WORKDIR /app

# Copy pre-built wheels from builder and install them (faster & reproducible)
COPY --from=builder /wheels /wheels
RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir /wheels/*

# Copy only application code after dependencies are installed
COPY . /app

# Ensure the app directory is owned by the unprivileged user
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Use Uvicorn directly; in production consider a process manager or Gunicorn with Uvicorn workers
CMD ["uvicorn", "wahl_bot.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
