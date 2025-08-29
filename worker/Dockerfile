# Use an official Python runtime
FROM python:3.12-slim

# Install system dependencies for headless Chrome
RUN apt-get update && apt-get install -y \
    wget gnupg unzip python3-setuptools \
    --no-install-recommends

# Install Chrome
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /etc/apt/trusted.gpg.d/google-chrome.gpg \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google.list \
    && apt-get update && apt-get install -y google-chrome-stable --no-install-recommends

# Download and install ChromeDriver
RUN CHROME_DRIVER_VERSION=$(wget -q -O - "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_STABLE") \
    && wget -q --continue -P /usr/local/bin/ "http://storage.googleapis.com/chrome-for-testing-public/${CHROME_DRIVER_VERSION}/linux64/chromedriver-linux64.zip" \
    && unzip /usr/local/bin/chromedriver-linux64.zip -d /usr/local/bin/ \
    && rm /usr/local/bin/chromedriver-linux64.zip

# Set working directory
WORKDIR /app

# Copy dependency file and install packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY scraper.py .
COPY worker.py .

# Run the web server on container startup
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "worker:app"]