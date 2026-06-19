#!/usr/bin/env python
"""
Development server startup script with proper environment configuration.
"""
import os
import sys
import django
from django.core.management import execute_from_command_line

if __name__ == "__main__":
    # Force SQLite for local development
    os.environ["DJANGO_DB_SQLITE"] = "True"
    os.environ["DJANGO_SETTINGS_MODULE"] = "project.settings"
    
    # Set other required environment variables
    os.environ.setdefault("DJANGO_SECRET_KEY", "dev-secret-key-123")
    os.environ.setdefault("DJANGO_DEBUG", "True")
    os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0")
    
    print("🚀 Starting Django development server with SQLite...")
    print("📊 Database: SQLite (local development)")
    print("🔧 Debug mode: ON")
    
    # Start the development server
    execute_from_command_line(["manage.py", "runserver", "0.0.0.0:8000"])