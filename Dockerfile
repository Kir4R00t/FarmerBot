FROM python:3.12-slim AS deps
WORKDIR /app

COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install -r requirements.txt

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN useradd -m -u 10001 appuser
WORKDIR /app

COPY --from=deps /opt/venv /opt/venv
COPY bot ./bot

USER appuser

CMD ["python", "-m", "bot.main"]