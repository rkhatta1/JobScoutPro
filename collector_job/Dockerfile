# Start with a Python base image
FROM python:3.12-slim

# Set environment variables to prevent interactive prompts during installation
ENV DEBIAN_FRONTEND=noninteractive

# 1. Install system dependencies, including jq for parsing JSON
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    jq \
    --no-install-recommends

# 2. Define the specific version we want to install
RUN CHROME_VERSION="139.0.7258.154" \
    && echo "Pinning Chrome and ChromeDriver to version: $CHROME_VERSION" \
    # 3. Fetch the official "Chrome for Testing" JSON data
    && JSON_URL="https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json" \
    && JSON_DATA=$(wget -q -O - "$JSON_URL") \
    # 4. Use jq to parse the JSON and find the download URLs for our specific version
    && CHROME_URL=$(echo "$JSON_DATA" | jq -r ".versions[] | select(.version==\"$CHROME_VERSION\") | .downloads.chrome[] | select(.platform==\"linux64\") | .url") \
    && DRIVER_URL=$(echo "$JSON_DATA" | jq -r ".versions[] | select(.version==\"$CHROME_VERSION\") | .downloads.chromedriver[] | select(.platform==\"linux64\") | .url") \
    # 5. Download and install the Chrome browser
    && echo "Downloading Chrome from: $CHROME_URL" \
    && wget -q --continue -P /tmp/ "$CHROME_URL" \
    && unzip /tmp/chrome-linux64.zip -d /opt/ \
    && rm /tmp/chrome-linux64.zip \
    # 6. Download and install the matching ChromeDriver
    && echo "Downloading ChromeDriver from: $DRIVER_URL" \
    && wget -q --continue -P /tmp/ "$DRIVER_URL" \
    && unzip /tmp/chromedriver-linux64.zip -d /usr/local/bin/ \
    && rm /tmp/chromedriver-linux64.zip \
    # 7. Create a symbolic link so the system can find the Chrome binary
    && ln -s /opt/chrome-linux64/chrome /usr/bin/google-chrome

# Set the working directory
WORKDIR /app

# Copy dependency file and install packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY scraper.py .

# Run the scraper script
CMD ["python3", "scraper.py"]