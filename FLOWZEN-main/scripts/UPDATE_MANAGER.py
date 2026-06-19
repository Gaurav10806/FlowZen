#!/usr/bin/env python3
"""
Update Manager - Automated update and maintenance script
Helps manage platform updates, backups, and monitoring
"""

import os
import sys
import subprocess
import json
import datetime
from pathlib import Path

class UpdateManager:
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.automation_dir = self.base_dir / "Automation"
        self.backup_dir = self.base_dir / "backups"
        self.backup_dir.mkdir(exist_ok=True)
        
    def run_command(self, command, cwd=None):
        """Run a shell command and return the result"""
        try:
            result = subprocess.run(
                command, 
                shell=True, 
                cwd=cwd or self.automation_dir,
                capture_output=True, 
                text=True
            )
            return result.returncode == 0, result.stdout, result.stderr
        except Exception as e:
            return False, "", str(e)
    
    def backup_database(self):
        """Create a database backup"""
        print("🔄 Creating database backup...")
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"backup_{timestamp}.json"
        
        success, stdout, stderr = self.run_command(
            f"python manage.py dumpdata > {backup_file}"
        )
        
        if success:
            print(f"✅ Database backup created: {backup_file}")
            return True
        else:
            print(f"❌ Backup failed: {stderr}")
            return False
    
    def run_tests(self):
        """Run the comprehensive test suite"""
        print("🧪 Running test suite...")
        
        success, stdout, stderr = self.run_command("python test_project.py")
        
        if success:
            print("✅ All tests passed!")
            return True
        else:
            print(f"❌ Tests failed: {stderr}")
            return False
    
    def check_dependencies(self):
        """Check if all dependencies are installed"""
        print("📦 Checking dependencies...")
        
        success, stdout, stderr = self.run_command("pip check")
        
        if success:
            print("✅ All dependencies are compatible")
            return True
        else:
            print(f"⚠️ Dependency issues found: {stderr}")
            return False
    
    def update_dependencies(self):
        """Update all dependencies to latest versions"""
        print("⬆️ Updating dependencies...")
        
        # Update pip first
        success, _, _ = self.run_command("python -m pip install --upgrade pip")
        if not success:
            print("❌ Failed to update pip")
            return False
        
        # Update all packages
        success, stdout, stderr = self.run_command("pip install -U -r requirements.txt")
        
        if success:
            print("✅ Dependencies updated successfully")
            return True
        else:
            print(f"❌ Dependency update failed: {stderr}")
            return False
    
    def collect_static_files(self):
        """Collect static files for production"""
        print("📁 Collecting static files...")
        
        success, stdout, stderr = self.run_command(
            "python manage.py collectstatic --noinput"
        )
        
        if success:
            print("✅ Static files collected")
            return True
        else:
            print(f"❌ Static file collection failed: {stderr}")
            return False
    
    def check_security(self):
        """Run Django security checks"""
        print("🔒 Running security checks...")
        
        success, stdout, stderr = self.run_command("python manage.py check --deploy")
        
        if success:
            print("✅ Security checks passed")
            return True
        else:
            print(f"⚠️ Security issues found: {stderr}")
            return False
    
    def optimize_database(self):
        """Run database optimization commands"""
        print("🗄️ Optimizing database...")
        
        # Run migrations
        success, _, stderr = self.run_command("python manage.py migrate")
        if not success:
            print(f"❌ Migration failed: {stderr}")
            return False
        
        # Analyze database (SQLite specific)
        success, _, _ = self.run_command("python manage.py dbshell < 'ANALYZE;'")
        
        print("✅ Database optimized")
        return True
    
    def generate_report(self, results):
        """Generate an update report"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        report = {
            "timestamp": timestamp,
            "results": results,
            "summary": {
                "total_checks": len(results),
                "passed": sum(1 for r in results.values() if r),
                "failed": sum(1 for r in results.values() if not r)
            }
        }
        
        report_file = self.backup_dir / f"update_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📊 Update Report Generated: {report_file}")
        print(f"✅ Passed: {report['summary']['passed']}")
        print(f"❌ Failed: {report['summary']['failed']}")
        
        return report
    
    def full_update(self):
        """Run a complete update cycle"""
        print("🚀 Starting Full Update Cycle")
        print("=" * 50)
        
        results = {}
        
        # Step 1: Backup
        results['backup'] = self.backup_database()
        
        # Step 2: Update dependencies
        results['dependencies'] = self.update_dependencies()
        
        # Step 3: Check dependencies
        results['dependency_check'] = self.check_dependencies()
        
        # Step 4: Run tests
        results['tests'] = self.run_tests()
        
        # Step 5: Collect static files
        results['static_files'] = self.collect_static_files()
        
        # Step 6: Security check
        results['security'] = self.check_security()
        
        # Step 7: Database optimization
        results['database_optimization'] = self.optimize_database()
        
        # Generate report
        report = self.generate_report(results)
        
        print("\n" + "=" * 50)
        if report['summary']['failed'] == 0:
            print("🎉 Update completed successfully!")
        else:
            print("⚠️ Update completed with some issues. Check the report for details.")
        
        return results
    
    def quick_check(self):
        """Run a quick health check"""
        print("⚡ Running Quick Health Check")
        print("-" * 30)
        
        results = {}
        
        # Quick tests
        results['tests'] = self.run_tests()
        results['dependency_check'] = self.check_dependencies()
        results['security'] = self.check_security()
        
        # Generate mini report
        passed = sum(1 for r in results.values() if r)
        total = len(results)
        
        print(f"\n📊 Quick Check Results: {passed}/{total} passed")
        
        if passed == total:
            print("✅ System is healthy!")
        else:
            print("⚠️ Issues detected. Run full update for details.")
        
        return results
    
    def maintenance_mode(self, enable=True):
        """Enable/disable maintenance mode"""
        maintenance_file = self.automation_dir / "maintenance.txt"
        
        if enable:
            with open(maintenance_file, 'w') as f:
                f.write(f"Maintenance mode enabled at {datetime.datetime.now()}")
            print("🔧 Maintenance mode enabled")
        else:
            if maintenance_file.exists():
                maintenance_file.unlink()
            print("✅ Maintenance mode disabled")

def main():
    manager = UpdateManager()
    
    if len(sys.argv) < 2:
        print("Usage: python UPDATE_MANAGER.py [command]")
        print("\nAvailable commands:")
        print("  full-update    - Run complete update cycle")
        print("  quick-check    - Run quick health check")
        print("  backup         - Create database backup")
        print("  test           - Run test suite")
        print("  dependencies   - Update dependencies")
        print("  security       - Run security checks")
        print("  maintenance    - Enable maintenance mode")
        print("  maintenance-off - Disable maintenance mode")
        return
    
    command = sys.argv[1].lower()
    
    if command == "full-update":
        manager.full_update()
    elif command == "quick-check":
        manager.quick_check()
    elif command == "backup":
        manager.backup_database()
    elif command == "test":
        manager.run_tests()
    elif command == "dependencies":
        manager.update_dependencies()
    elif command == "security":
        manager.check_security()
    elif command == "maintenance":
        manager.maintenance_mode(True)
    elif command == "maintenance-off":
        manager.maintenance_mode(False)
    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main()