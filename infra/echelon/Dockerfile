FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    psycopg2-binary==2.9.10 \
    httpx==0.28.1

COPY echelon.py .

CMD ["python", "-u", "echelon.py"]
