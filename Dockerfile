FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for Pillow and other packages
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import os; exit(0 if os.path.exists('logs/activity.log') else 1)"

# Run the application
CMD ["python", "main.py"]
