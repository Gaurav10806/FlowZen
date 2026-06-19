@echo off
echo ========================================
echo   Workflow Automation Platform
echo   Starting Development Server...
echo ========================================
echo.

cd Automation

echo Setting up environment...
set DJANGO_DB_SQLITE=True

echo.
echo Starting Django development server...
echo.
echo Access your platform at:
echo   Main UI: http://127.0.0.1:8000/
echo   Admin Panel: http://127.0.0.1:8000/admin/
echo   User App: http://127.0.0.1:8000/user-app/
echo   API: http://127.0.0.1:8000/api/
echo.
echo Press Ctrl+C to stop the server
echo.

python manage.py runserver