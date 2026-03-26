# PINNED: verified clean 2026-03-25 TPCP-2026-0324 — DO NOT upgrade without security review
# python:3.12-slim → pinned to digest below
FROM python:3.12-slim@sha256:3d5ed973e45820f5ba5e46bd065bd88b3a504ff0724d85980dcd05eab361fcf4
RUN pip install --no-cache-dir prometheus-client
COPY nvidia_smi_exporter.py /app/
WORKDIR /app
CMD ["python", "nvidia_smi_exporter.py"]
