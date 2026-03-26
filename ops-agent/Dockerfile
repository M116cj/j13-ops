# PINNED: verified clean 2026-03-25 TPCP-2026-0324 — DO NOT upgrade without security review
# python:3.12-slim → pinned to digest below
FROM python:3.12-slim@sha256:3d5ed973e45820f5ba5e46bd065bd88b3a504ff0724d85980dcd05eab361fcf4

WORKDIR /app

# Install docker CLI (used via subprocess for container management)
RUN apt-get update \
    && apt-get install -y --no-install-recommends docker.io \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-u", "agent.py"]
