# FlowZen Production Deployment Guide

This guide provides step-by-step deployment instructions for hosting **FlowZen** across **Railway**, **Render**, **Docker Compose**, and **Self-Hosted VPS (Ubuntu/Nginx)**.

---

## Architecture Overview

FlowZen requires 5 processes/services in production:

```
┌─────────────────────────────────────────────────────────────┐
│                    HTTP / HTTPS Ingress                     │
└──────────────────────────────┬──────────────────────────────┘
                               │
               ┌───────────────┴───────────────┐
               │  FlowZen Web Service (ASGI)   │
               │ Gunicorn + Uvicorn ($PORT)    │
               └───────┬───────────────┬───────┘
                       │               │
      ┌────────────────┴┐             ┌┴────────────────┐
      │  PostgreSQL 16  │             │     Redis 7     │
      │   Database      │             │  Broker & Cache │
      └────────────────┬┘             └┬────────────────┘
                       │               │
               ┌───────┴───────────────┴───────┐
               │    Celery Async Worker        │
               └───────────────┬───────────────┘
                               │
               ┌───────────────┴───────────────┐
               │    Celery Beat Scheduler      │
               └───────────────────────────────┘
```

---

## 1. Required Infrastructure Services

1. **PostgreSQL Database** (v15 or v16)
2. **Redis Instance** (v6 or v7)
3. **Web Application Container** (`web`)
4. **Celery Worker Container** (`worker`)
5. **Celery Beat Scheduler Container** (`beat`)

---

## 2. Essential Production Environment Variables

Ensure these environment variables are set in your platform secrets manager:

```env
# General & Site Configuration
SITE_URL=https://flowzen.yourdomain.com
PORT=8000
WEB_CONCURRENCY=4

# Django Core & Security
DJANGO_SECRET_KEY=generate-a-secure-random-64-char-string
DJANGO_DEBUG=False
ALLOWED_HOSTS=flowzen.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://flowzen.yourdomain.com

# Database (Provide EITHER DATABASE_URL OR individual parameters)
DATABASE_URL=postgresql://user:password@host:5432/flowzen_db

# Redis & Celery
REDIS_URL=redis://redis-host:6379/0
CELERY_BROKER_URL=redis://redis-host:6379/0
CELERY_RESULT_BACKEND=redis://redis-host:6379/0

# AI Provider Architecture
AI_PROVIDER=gemini
GEMINI_API_KEY=your-actual-google-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash

# Security & Encryption
CREDENTIALS_MASTER_KEY=IeOn9kTi1EaZWc2cgToDvqJq9PjrZe8oi-FOlhDwZaM=
```

---

## 3. Platform Specific Deployment Guides

### Option A: Railway Deployment

1. **New Project**: Create a new project on Railway.
2. **Add Databases**: Add **PostgreSQL** and **Redis** database plugins from Railway template.
3. **Deploy Web Service**:
   - Connect your GitHub repository.
   - Set Build Command: Leave blank (Railway automatically detects `Dockerfile`).
   - Set Start Command: `python docker_startup_with_templates.py`
   - Add Environment Variables: Copy from the table above. Railway automatically injects `DATABASE_URL`, `REDIS_URL`, and `PORT`.
4. **Deploy Worker Service**:
   - Add a new service referencing the same repository.
   - Set Start Command: `python start_worker_safe.py`
5. **Deploy Beat Service**:
   - Add a new service referencing the same repository.
   - Set Start Command: `python start_beat_safe.py`

---

### Option B: Render Deployment

1. **New Blueprint or Services**:
   - Create a **PostgreSQL** database instance.
   - Create a **Redis** instance.
2. **Web Service (`web`)**:
   - Environment: `Docker`
   - Build Command: Left empty (built via `Dockerfile`)
   - Start Command: `python docker_startup_with_templates.py`
   - Health Check Path: `/healthz` or `/api/v1/health/`
3. **Background Worker (`worker`)**:
   - Environment: `Docker`
   - Start Command: `python start_worker_safe.py`
4. **Cron / Background Worker (`beat`)**:
   - Environment: `Docker`
   - Start Command: `python start_beat_safe.py`

---

### Option C: Docker Compose (Self-Hosted VPS)

1. Clone repository on your VPS:
   ```bash
   git clone https://github.com/Gaurav10806/FlowZen.git
   cd FlowZen
   ```

2. Create production `.env` file:
   ```bash
   cp Automation/backend/.env.production.example .env
   # Edit .env and supply DJANGO_SECRET_KEY, GEMINI_API_KEY, SITE_URL
   ```

3. Launch production stack:
   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   ```

4. Verify status:
   ```bash
   docker compose -f docker-compose.prod.yml ps
   ```

---

## 4. Health Check Endpoints

FlowZen exposes standardized zero-auth health endpoints for container probes and load balancers:

- `/healthz`
- `/health/`
- `/api/v1/health/`

Expected Response (`HTTP 200 OK`):
```json
{
  "status": "healthy",
  "database": "connected",
  "cache": "working",
  "timestamp": 1770854400.0
}
```

---

## 5. Migration & Maintenance Strategy

- Database migrations execute automatically during web container boot via `docker_startup_with_templates.py`.
- To trigger manual migration:
  ```bash
  python manage.py migrate --noinput
  ```
- To toggle maintenance mode, create a `maintenance.txt` file in the project root:
  ```bash
  touch maintenance.txt
  ```
