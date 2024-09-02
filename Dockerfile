FROM python:3.10-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    xvfb \
    chromium \
    chromium-driver \
    libxi6 \
    libgconf-2-4 \
    libnss3 \
    libxss1 \
    libappindicator3-1 \
    libatk1.0-0 \
    libdbus-glib-1-2 \
    libgbm-dev \
    libgtk-3-0 \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libgbm1 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install selenium python-dotenv pytz beautifulsoup4

# Set the display port to avoid errors
ENV DISPLAY=:99

# Set the working directory
WORKDIR /app

# Add a script to run the browser
CMD ["python", "-u", "/run_browser.py"]
