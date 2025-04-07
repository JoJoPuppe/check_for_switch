FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (for lxml and other libs)
RUN apt-get update && apt-get install -y \
    gcc \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies file first (for Docker caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the actual script
COPY get_a_switch2.py .

# Copy .env if you're using it (optional)
# COPY .env .

# Set environment variables (or pass them via `docker run -e`)
# ENV TELEGRAM_TOKEN=your_token_here
# ENV TELEGRAM_CHAT_ID=your_chat_id_here

# Run the script
CMD ["python", "get_a_switch2.py"]

