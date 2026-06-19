import sys
import subprocess

def run_linter():
    """Run linting checks."""
    print("🧹 Running Linter (Flake8)...")
    
    try:
        # Check if flake8 is installed (it might not be in prod env)
        subprocess.run([sys.executable, "-m", "flake8", "--version"], check=True, stdout=subprocess.DEVNULL)
        
        # Run flake8 on project
        result = subprocess.run([sys.executable, "-m", "flake8", "project", "workflows", "--max-line-length=120"], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Linting Passed!")
        else:
            print("⚠️ Linting Issues Found:")
            print(result.stdout)
            # We don't fail build for now, just warn
            
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️ Flake8 not installed or found. Skipping linting.")

if __name__ == "__main__":
    run_linter()
