FROM python:3.13-alpine@sha256:7415fbc3c9e4979cc717d92377ab2bc7b2b4a2af1ac03cc52b5f3f88efedaf3a AS builder
COPY --from=ghcr.io/astral-sh/uv:0.12.14@sha256:1946145b8706ad9e5c0e79a513f9e324b58d5e38126bb2c8b7dbfca61febeb45 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.13-alpine@sha256:7415fbc3c9e4979cc717d92377ab2bc7b2b4a2af1ac03cc52b5f3f88efedaf3a AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/app/.venv/bin:$PATH" \
    GATEWAY_HOST=0.0.0.0
WORKDIR /app
RUN apk upgrade --no-cache \
    && rm -rf /usr/local/lib/python*/site-packages/pip* \
        /usr/local/lib/python*/site-packages/setuptools* \
        /usr/local/lib/python*/ensurepip \
        /usr/local/bin/pip* \
    && addgroup -g 10001 -S gateway \
    && adduser -u 10001 -S -D -H -G gateway gateway
COPY --from=builder --chown=10001:10001 /app/.venv /app/.venv
COPY --chown=10001:10001 config /app/config
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).close()"]
ENTRYPOINT ["fastmcp-gateway"]
CMD ["serve"]

FROM runtime AS lambda
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:1.0.1@sha256:1e5ab4d9242167500ed8a7bed8a79b448228aaa51cf382fb51fe4bf8a5f9a811 /lambda-adapter /opt/extensions/lambda-adapter
ENV AWS_LWA_PORT=8000 AWS_LWA_READINESS_CHECK_PATH=/healthz \
    AWS_LWA_READINESS_CHECK_HEALTHY_STATUS=200 AWS_LWA_INVOKE_MODE=buffered
