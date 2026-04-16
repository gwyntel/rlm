FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY rlm/ ./rlm/

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["fastmcp", "run", "rlm.server:mcp", "--transport", "http", "--host", "0.0.0.0", "--port", "8000"]
