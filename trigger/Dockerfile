# Start with a standard Python base image
FROM python:3.12-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the job trigger service
COPY job_trigger_service.py .

# Run as a Flask service with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--timeout", "60", "job_trigger_service:app"]