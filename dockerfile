# ----- base: resolve dependencies separately for caching -----
FROM python:3.12-slim AS deps
WORKDIR /app

# If using requirements.txt:
COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install -r requirements.txt

# ----- runtime image -----
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# Create a non-root user
RUN useradd -m -u 10001 appuser
WORKDIR /app

# Copy venv from deps stage
COPY --from=deps /opt/venv /opt/venv

# Copy source
COPY bot ./bot

# Drop privileges
USER appuser

# Default command (run the bot)
CMD ["python", "-m", "bot.main"]