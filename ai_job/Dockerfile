# Start with a standard Python base image
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# We no longer need scraper.py for this service
COPY ai_analyzer.py .

ENTRYPOINT ["python3", "ai_analyzer.py"]
CMD ["--urls-json", "[]", "--batch-id", "default"]