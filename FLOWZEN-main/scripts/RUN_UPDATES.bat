@echo off
echo ========================================
echo   Workflow Platform Update Manager
echo ========================================
echo.

:menu
echo Choose an option:
echo 1. Quick Health Check
echo 2. Full Update Cycle
echo 3. Backup Database Only
echo 4. Run Tests Only
echo 5. Update Dependencies
echo 6. Security Check
echo 7. Exit
echo.

set /p choice="Enter your choice (1-7): "

if "%choice%"=="1" goto quick_check
if "%choice%"=="2" goto full_update
if "%choice%"=="3" goto backup
if "%choice%"=="4" goto test
if "%choice%"=="5" goto dependencies
if "%choice%"=="6" goto security
if "%choice%"=="7" goto exit
goto invalid

:quick_check
echo.
echo Running Quick Health Check...
python UPDATE_MANAGER.py quick-check
pause
goto menu

:full_update
echo.
echo Running Full Update Cycle...
echo This may take several minutes...
python UPDATE_MANAGER.py full-update
pause
goto menu

:backup
echo.
echo Creating Database Backup...
python UPDATE_MANAGER.py backup
pause
goto menu

:test
echo.
echo Running Test Suite...
python UPDATE_MANAGER.py test
pause
goto menu

:dependencies
echo.
echo Updating Dependencies...
python UPDATE_MANAGER.py dependencies
pause
goto menu

:security
echo.
echo Running Security Checks...
python UPDATE_MANAGER.py security
pause
goto menu

:invalid
echo Invalid choice. Please try again.
goto menu

:exit
echo.
echo Goodbye!
pause