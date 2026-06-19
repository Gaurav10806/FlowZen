# Production Dockerfile
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install gunicorn

# Copy project files
COPY backend/ /app/
COPY frontend/ /app/frontend/

# Create directory for static files and logs
RUN mkdir -p /app/staticfiles /app/media /app/logs

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Expose port
EXPOSE 8000

# Entrypoint script (optional, can be done in CMD)
# Validating environment variables before start
CMD ["sh", "-c", "python scripts/validate_env.py && gunicorn project.wsgi:application --bind 0.0.0.0:8000 --workers 3 --threads 2"]