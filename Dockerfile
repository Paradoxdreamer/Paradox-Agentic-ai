FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as non-root. This matters more than usual here: executor.py executes
# agent-generated shell commands (see its module docstring), and
# containerizing + dropping root is exactly the mitigation that warning
# asks for -- it doesn't make execution "safe", but it meaningfully
# shrinks the blast radius of a bad generation.
RUN useradd --create-home --uid 1000 paradox \
    && mkdir -p /app/workspace \
    && chown -R paradox:paradox /app
USER paradox

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/meta || exit 1

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
