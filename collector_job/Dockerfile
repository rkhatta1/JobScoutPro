# Start with a Python base image
FROM python:3.12-slim

# Set environment variables to prevent interactive prompts during installation
ENV DEBIAN_FRONTEND=noninteractive

# 1. Define the pinned version at the top for easy updates
# The base version is for the driver, the package version is for apt-get.
ENV CHROME_VERSION_BASE="141.0.7390.54"
ENV CHROME_PACKAGE_VERSION="141.0.7390.54-1"

# 2. Install system dependencies, including jq for parsing JSON
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    jq \
    --no-install-recommends

# 3. Add Google Chrome's official GPG key and repository
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /etc/apt/trusted.gpg.d/google-chrome.gpg \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google.list

# 4. Install the PINNED version of Google Chrome.
# apt-get will automatically handle all necessary shared library dependencies.
RUN apt-get update && apt-get install -y \
    google-chrome-stable=${CHROME_PACKAGE_VERSION} \
    --no-install-recommends

# 5. Download and install the EXACT MATCHING version of ChromeDriver
# We use the base version to query the official "Chrome for Testing" endpoint.
RUN echo "Fetching ChromeDriver for version ${CHROME_VERSION_BASE}..." \
    && DRIVER_URL=$(wget -q -O - "https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json" | jq -r ".versions[] | select(.version==\"$CHROME_VERSION_BASE\") | .downloads.chromedriver[] | select(.platform==\"linux64\") | .url") \
    && echo "Downloading ChromeDriver from: $DRIVER_URL" \
    && wget -q --continue -P /tmp/ "$DRIVER_URL" \
    && unzip /tmp/chromedriver-linux64.zip -d /usr/local/bin/ \
    && rm /tmp/chromedriver-linux64.zip

# Set the working directory
WORKDIR /app

# Copy dependency file and install packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY scraper.py .

# Run the scraper script
CMD ["python3", "scraper.py"]
