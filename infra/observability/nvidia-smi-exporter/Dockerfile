FROM python:3.12-slim
RUN pip install --no-cache-dir prometheus-client
COPY nvidia_smi_exporter.py /app/
WORKDIR /app
CMD ["python", "nvidia_smi_exporter.py"]
