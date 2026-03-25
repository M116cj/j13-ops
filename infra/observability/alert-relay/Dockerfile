FROM python:3.12-slim
RUN pip install --no-cache-dir flask requests
COPY alert_relay.py /app/
WORKDIR /app
CMD ["python", "alert_relay.py"]
