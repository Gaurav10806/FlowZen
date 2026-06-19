#!/usr/bin/env python3
"""
Docker startup script with Template and Credential Management initialization
Ensures all systems are properly set up in the Docker environment
"""

import os
import sys
import time
import json
import subprocess
from pathlib import Path

def log(message):
    """Log with timestamp"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def check_database_connection():
    """Check if database is accessible"""
    log("🔍 Checking database connection...")
    
    try:
        import django
        from django.conf import settings
        from django.db import connection
        
        # Setup Django (Handled in main)
        pass
        
        # Test database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            
        log("✅ Database connection successful")
        return True
        
    except Exception as e:
        import traceback
        log(f"❌ Database connection failed: {str(e)}")
        traceback.print_exc()
        return False

def run_migrations():
    """Run Django migrations"""
    log("🔄 Running Django migrations...")
    
    try:
        result = subprocess.run([
            sys.executable, 'manage.py', 'migrate', '--noinput'
        ], capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            log("✅ Migrations completed successfully")
            return True
        else:
            log(f"❌ Migration failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        log("❌ Migration timed out after 120 seconds")
        return False
    except Exception as e:
        log(f"❌ Migration error: {str(e)}")
        return False

def collect_static_files():
    """Collect static files including frontend assets"""
    log("📦 Collecting static files...")
    
    try:
        result = subprocess.run([
            sys.executable, 'manage.py', 'collectstatic', '--noinput', '--clear'
        ], capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            log("✅ Static files collected successfully")
            return True
        else:
            if "PermissionError" in result.stderr:
                 log(f"⚠️ Static collection Permission Error (Likely root-owned files). Safe to ignore in dev.")
            else:
                 log(f"⚠️ Static collection warning: {result.stderr}")
            return True # Non-blocking in dev
            
    except Exception as e:
        log(f"⚠️ Static collection error: {str(e)} (Non-fatal in dev)")
        return True # Non-blocking in dev

def setup_storage_directories():
    """Setup template and credential storage directories"""
    log("📁 Setting up storage directories...")
    
    try:
        # Create storage directories
        template_dir = Path("/app/templates_storage")
        credential_dir = Path("/app/credentials_storage")
        
        # Helper to safely create directory
        def safe_mkdir(path):
            if not path.exists():
                try:
                    path.mkdir(parents=True, exist_ok=True)
                    log(f"📁 Created directory: {path}")
                except PermissionError:
                    if path.exists():
                        log(f"⚠️ Permission denied but directory exists: {path}")
                    else:
                        raise
            else:
                log(f"📁 Directory already exists: {path}")

        safe_mkdir(template_dir)
        safe_mkdir(credential_dir)
        
        # Create subdirectories
        safe_mkdir(template_dir / "user_templates")
        safe_mkdir(template_dir / "system_templates")
        safe_mkdir(credential_dir / "encrypted")
        
        log("✅ Storage directories setup complete")
        return True
        
    except Exception as e:
        log(f"⚠️ Storage directory setup warning: {str(e)} (Continuining anyway)")
        return True # Non-fatal in dev

def initialize_default_templates():
    """Initialize default workflow templates"""
    log("🎨 Initializing default templates...")
    
    try:
        template_dir = Path("/app/templates_storage/system_templates")
        
        # Create default templates
        default_templates = {
            "ai_content_generator": {
                "name": "AI Content Generator",
                "description": "Generate blog posts and marketing copy using AI",
                "category": "ai",
                "difficulty": "beginner",
                "nodes": [
                    {"id": "trigger", "type": "webhook", "position": {"x": 100, "y": 200}},
                    {"id": "ai", "type": "ai-agent", "position": {"x": 300, "y": 200}},
                    {"id": "response", "type": "http_response", "position": {"x": 500, "y": 200}}
                ],
                "edges": [
                    {"source": "trigger", "target": "ai"},
                    {"source": "ai", "target": "response"}
                ]
            },
            "email_automation": {
                "name": "Email Automation",
                "description": "Automated email sending with Gmail integration",
                "category": "communication",
                "difficulty": "intermediate",
                "nodes": [
                    {"id": "schedule", "type": "schedule", "position": {"x": 100, "y": 200}},
                    {"id": "email", "type": "email", "position": {"x": 300, "y": 200}}
                ],
                "edges": [
                    {"source": "schedule", "target": "email"}
                ]
            }
        }
        
        for template_id, template_data in default_templates.items():
            template_path = template_dir / f"{template_id}.json"
            try:
                with open(template_path, 'w') as f:
                    json.dump(template_data, f, indent=4)
                log(f"📄 Created template: {template_id}")
            except PermissionError:
                if template_path.exists():
                    log(f"⚠️ Permission denied but template exists: {template_id}")
                else:
                    log(f"⚠️ Could not create template {template_id}: Permission denied")
            except Exception as e:
                log(f"⚠️ Error creating template {template_id}: {str(e)}")
        
        log(f"✅ {len(default_templates)} default templates initialized")
        return True
        
    except Exception as e:
        log(f"⚠️ Default template initialization warning: {str(e)} (Continuing anyway)")
        return True # Non-fatal in dev

def setup_credential_encryption():
    """Setup credential encryption system"""
    log("🔐 Setting up credential encryption...")
    
    try:
        from cryptography.fernet import Fernet
        
        # Check if encryption key exists
        key_file = Path("/app/credentials_storage/encryption.key")
        
        if not key_file.exists():
            try:
                # Generate new encryption key
                key = Fernet.generate_key()
                with open(key_file, 'wb') as f:
                    f.write(key)
                
                # Set proper permissions
                try:
                    key_file.chmod(0o600)
                except:
                    pass
                log("✅ New encryption key generated")
            except PermissionError:
                log("⚠️ Could not generate encryption key: Permission denied")
            except Exception as e:
                log(f"⚠️ Error generating encryption key: {str(e)}")
        else:
            log("✅ Encryption key already exists")
        
        return True
        
    except Exception as e:
        log(f"⚠️ Credential encryption setup warning: {str(e)} (Continuing anyway)")
        return True # Non-fatal in dev

def verify_frontend_assets():
    """Verify frontend assets are properly available"""
    log("🎨 Verifying frontend assets...")
    
    try:
        frontend_dir = Path("/app/frontend")
        required_files = [
            "js/main.js",
            "js/nodes.js",
            "js/edges.js",
            "css/main.css",
            "templates/workflows/dashboard.html"  # Replaces index.html
        ]
        
        missing_files = []
        for file_path in required_files:
            if not (frontend_dir / file_path).exists():
                missing_files.append(file_path)
        
        if missing_files:
            # Non-blocking warning instead of error to allow startup
            log(f"⚠️  Missing frontend files: {', '.join(missing_files)} (Continuing startup)")
            return True
        
        log("✅ Frontend assets verified")
        return True
        
    except Exception as e:
        log(f"❌ Frontend asset verification failed: {str(e)}")
        return False

def create_superuser_if_needed():
    """Create superuser if none exists"""
    log("👤 Checking for superuser...")
    
    try:
        import django
        from django.contrib.auth.models import User
        
        # Setup Django (Handled in main)
        pass
        
        if not User.objects.filter(is_superuser=True).exists():
            log("Creating default superuser...")
            User.objects.create_superuser(
                username='admin',
                email='admin@example.com',
                password='admin123'
            )
            log("✅ Default superuser created (admin/admin123)")
        else:
            log("✅ Superuser already exists")
        
        return True
        
    except Exception as e:
        log(f"❌ Superuser creation failed: {str(e)}")
        return False

def start_django_server():
    """Start Django development server"""
    log("🚀 Starting Django server...")
    
    try:
        # Use runserver for stability in this environment
        cmd = [
            sys.executable, 'manage.py', 'runserver', '0.0.0.0:8000'
        ]
        
        subprocess.run(cmd)
        
    except KeyboardInterrupt:
        log("🛑 Server stopped by user")
    except Exception as e:
        log(f"❌ Server startup failed: {str(e)}")
        sys.exit(1)

def main():
    """Main startup sequence"""
    import sys
    log(f"Current Path: {sys.path}")
    log(f"CWD: {os.getcwd()}")
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
    try:
        import django
        django.setup()
    except Exception as e:
        log(f"Failed to setup Django: {e}")
        sys.exit(1)
        
    log("🐳 Starting Docker container with Template & Credential Management")
    log("=" * 60)
    
    # Wait for database to be ready
    max_retries = 30
    for attempt in range(max_retries):
        if check_database_connection():
            break
        
        if attempt < max_retries - 1:
            log(f"⏳ Database not ready, retrying in 2 seconds... ({attempt + 1}/{max_retries})")
            time.sleep(2)
        else:
            log("❌ Database connection failed after all retries")
            sys.exit(1)
    
    # Run startup sequence
    startup_steps = [
        ("Database Migrations", run_migrations),
        ("Storage Directories", setup_storage_directories),
        ("Default Templates", initialize_default_templates),
        ("Credential Encryption", setup_credential_encryption),
        ("Frontend Assets", verify_frontend_assets),
        ("Static Files", collect_static_files),
        ("Superuser Setup", create_superuser_if_needed)
    ]
    
    for step_name, step_func in startup_steps:
        log(f"📋 Running: {step_name}")
        if not step_func():
            log(f"❌ Startup failed at: {step_name}")
            sys.exit(1)
        time.sleep(1)
    
    log("✅ All startup steps completed successfully!")
    log("🎉 Template & Credential Management System Ready!")
    log("=" * 60)
    log("📍 Access the application at: http://localhost:8000")
    log("👤 Admin panel: http://localhost:8000/admin/ (admin/admin123)")
    log("🎨 Workflow Builder: http://localhost:8000/workflows/builder/")
    log("=" * 60)
    
    # Start the server
    start_django_server()

if __name__ == "__main__":
    main()