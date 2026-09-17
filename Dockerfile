FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MODEL_PATH=/app/models/uci-real-estate-ridge-v1.json

WORKDIR /app
COPY --from=builder /install /usr/local
COPY models ./models

RUN groupadd --gid 10001 app && \
    useradd --uid 10001 --gid app --no-create-home app && \
    chown -R app:app /app

USER 10001:10001
EXPOSE 8000

CMD ["uvicorn", "house_price_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
