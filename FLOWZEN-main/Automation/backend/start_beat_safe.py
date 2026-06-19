#!/usr/bin/env python3
"""
CRITICAL: Safe Celery Beat startup script
Ensures DB and Redis are ready before starting Beat
Prevents ^ ^ ^ ^ spam and silent failures
"""

import os
import sys
import time
import django
import redis
from django.db import connection
from django.core.management import execute_from_command_line

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

def check_beat_tables():
    """Verify django-celery-beat tables exist"""
    print("🔍 Checking django-celery-beat tables...")
    
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name LIKE 'django_celery_beat_%'
            """)
            table_count = cursor.fetchone()[0]
            
            if table_count >= 4:  # Should have at least 4 beat tables
                print(f"✅ django-celery-beat tables found ({table_count} tables)")
                return True
            else:
                print(f"❌ Insufficient Beat tables found ({table_count} tables)")
                return False
    except Exception as e:
        print(f"❌ Error checking Beat tables: {e}")
        return False

def apply_migrations():
    """Apply all migrations including django-celery-beat"""
    print("🔧 Applying migrations...")
    
    try:
        # Apply all migrations
        execute_from_command_line(['manage.py', 'migrate'])
        print("✅ All migrations applied")
        return True
    except Exception as e:
        print(f"❌ Error applying migrations: {e}")
        return False

def start_beat():
    """Start Celery Beat with DatabaseScheduler"""
    print("🚀 Starting Celery Beat with DatabaseScheduler...")
    
    try:
        # Use explicit DatabaseScheduler
        os.execvp('celery', [
            'celery',
            '-A', 'project',
            'beat',
            '-l', 'info',
            '--scheduler', 'django_celery_beat.schedulers:DatabaseScheduler'
        ])
    except Exception as e:
        print(f"❌ Error starting Beat: {e}")
        return False

def main():
    """Main startup sequence"""
    print("🔥 CELERY BEAT SAFE STARTUP")
    print("=" * 40)
    
    # Step 1: Wait for dependencies
    if not wait_for_db():
        print("❌ FATAL: Database not available")
        sys.exit(1)
    
    if not wait_for_redis():
        print("❌ FATAL: Redis not available")
        sys.exit(1)
    
    # Step 2: Ensure migrations are applied
    if not apply_migrations():
        print("❌ FATAL: Migration failed")
        sys.exit(1)
    
    # Step 3: Verify Beat tables exist
    if not check_beat_tables():
        print("❌ FATAL: Beat tables missing")
        sys.exit(1)
    
    # Step 4: Start Beat
    print("✅ All dependencies ready - starting Beat")
    start_beat()

if __name__ == "__main__":
    main()