# Start with a standard Python base image
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# We no longer need scraper.py for this service
COPY ai_analyzer.py .

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--timeout", "540", "ai_analyzer:app"]