# Start with a standard Python base image
FROM python:3.12-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the dispatcher application code
COPY dispatcher.py .

# Command to run the Gunicorn web server on container startup
# It will serve the 'app' object from the 'dispatcher.py' file.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "dispatcher:app"]