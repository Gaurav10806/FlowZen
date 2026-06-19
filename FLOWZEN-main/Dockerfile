FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=project.settings

WORKDIR /app

# System dependencies for psycopg2 and build steps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies - FIXED: Use correct nested path
COPY Automation/backend/requirements.txt .
RUN pip install --no-cache-dir "setuptools<70.0.0" && \
    pip install --no-cache-dir -r requirements.txt

# Copy Django project files - FIXED: Use correct nested path
COPY Automation/backend/ .

# Copy frontend files to serve static assets - FIXED: Use correct nested path
ARG CACHEBUST=1
COPY Automation/frontend/ ./frontend/

# Copy startup and health check scripts
COPY Automation/backend/docker_startup_with_templates.py .
COPY Automation/backend/docker_healthcheck.py .

# Create directories for template and credential storage
RUN mkdir -p /app/media /app/templates_storage /app/credentials_storage

# Collect static assets (can be skipped in dev by overriding the command)
RUN python manage.py collectstatic --noinput || true

# Create non-root user for security
RUN adduser --disabled-password --gecos '' --uid 1000 appuser && \
    chown -R appuser:appuser /app && \
    chmod 755 /app/templates_storage /app/credentials_storage
USER appuser

EXPOSE 8000

# Default command (overridden in docker-compose)
CMD ["python", "docker_startup_with_templates.py"]