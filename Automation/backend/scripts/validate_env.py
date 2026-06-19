import os
import sys
import socket

def check_env_vars():
    """Check definition of critical environment variables."""
    required_vars = [
        "SECRET_KEY", 
        "DATABASE_HOST", "DATABASE_NAME", "DATABASE_USER", "DATABASE_PASSWORD",
        "REDIS_URL"
    ]
    
    missing = [var for var in required_vars if not os.environ.get(var)]
    
    if missing:
        print(f"❌ CRITICAL ERROR: Missing environment variables: {', '.join(missing)}")
        if not os.environ.get("DEBUG", "False") == "True":
             sys.exit(1)
        else:
             print("⚠️  Running in DEBUG mode, continuing despite missing vars (Development Mode)")

def check_db_connection():
    """Check basic TCP connection to database port."""
    host = os.environ.get("DATABASE_HOST", "localhost")
    port = int(os.environ.get("DATABASE_PORT", 5432))
    
    try:
        sock = socket.create_connection((host, port), timeout=3)
        sock.close()
        print(f"✅ Database connection reachable ({host}:{port})")
    except Exception as e:
        print(f"❌ Database connection failed ({host}:{port}): {e}")
        # We don't exit here because Django might be waiting for DB to wake up (depends_on handles start order, but not readiness sometimes)

if __name__ == "__main__":
    print("🚀 Validating Environment...")
    check_env_vars()
    check_db_connection()
    print("✅ Environment Validation Complete.")
