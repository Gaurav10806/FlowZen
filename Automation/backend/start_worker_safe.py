#!/usr/bin/env python3
"""
CRITICAL: Safe Celery Worker startup script
Ensures DB and Redis are ready before starting Worker
"""

import os
import sys
import time
import django
import redis
from django.db import connection

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
django.setup()

def wait_for_db(max_attempts=30):
    """Wait for database to be ready"""
    print("🔍 Waiting for database...")
    
    for attempt in range(max_attempts):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            print("✅ Database is ready")
            return True
        except Exception as e:
            print(f"⏳ Database not ready (attempt {attempt + 1}/{max_attempts}): {e}")
            time.sleep(2)
    
    print("❌ Database failed to become ready")
    return False

def wait_for_redis(max_attempts=30):
    """Wait for Redis to be ready"""
    print("🔍 Waiting for Redis...")
    
    redis_url = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
    
    for attempt in range(max_attempts):
        try:
            r = redis.from_url(redis_url)
            r.ping()
            print("✅ Redis is ready")
            return True
        except Exception as e:
            print(f"⏳ Redis not ready (attempt {attempt + 1}/{max_attempts}): {e}")
            time.sleep(2)
    
    print("❌ Redis failed to become ready")
    return False

def start_worker():
    """Start Celery Worker"""
    print("🚀 Starting Celery Worker...")
    
    try:
        os.execvp('celery', [
            'celery',
            '-A', 'project',
            'worker',
            '-l', 'info',
            '--concurrency=2'
        ])
    except Exception as e:
        print(f"❌ Error starting Worker: {e}")
        return False

def main():
    """Main startup sequence"""
    print("🔥 CELERY WORKER SAFE STARTUP")
    print("=" * 40)
    
    # Step 1: Wait for dependencies
    if not wait_for_db():
        print("❌ FATAL: Database not available")
        sys.exit(1)
    
    if not wait_for_redis():
        print("❌ FATAL: Redis not available")
        sys.exit(1)
    
    # Step 2: Start Worker
    print("✅ All dependencies ready - starting Worker")
    start_worker()

if __name__ == "__main__":
    main()