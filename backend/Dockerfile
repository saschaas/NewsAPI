FROM python:3.11-slim as base

# Install system dependencies for Playwright (Chromium + Firefox) and app
RUN apt-get update && apt-get install -y \
    ffmpeg \
    wget \
    # Shared Playwright dependencies
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    # Firefox-specific dependencies
    libgtk-3-0 \
    libdbus-glib-1-2 \
    libxt6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories
RUN mkdir -p /app/data /app/downloads

# Create non-root user and set permissions
RUN groupadd -r appuser && useradd -r -g appuser appuser -d /home/appuser
RUN mkdir -p /home/appuser/.cache
RUN chown -R appuser:appuser /app /home/appuser

# Switch to non-root user BEFORE installing browsers so they land in appuser's cache
USER appuser

# Install Playwright browsers
RUN playwright install chromium firefox

EXPOSE 8000

# Run database initialization and start server
CMD ["sh", "-c", "python -m app.init_db && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
