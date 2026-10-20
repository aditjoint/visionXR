@echo off
REM ========================================================================
REM    VISIONXR ENTERPRISE PRODUCTION NODE INSTALLER (WINDOWS)
REM    Sovereign AI Surveillance & Industrial Safety Governance
REM ========================================================================
setlocal enabledelayedexpansion

echo ========================================================================
echo    VISIONXR ENTERPRISE PRODUCTION NODE INSTALLER (WINDOWS)
echo ========================================================================

set "INSTALL_DIR=C:\VisionXR"
set "SCRIPT_DIR=%~dp0"
set "PACKAGE_ROOT=%SCRIPT_DIR%.."

echo.
echo [1/6] CUSTOMER STORAGE CONFIGURATION:
set "DEFAULT_STORAGE=C:\VisionXR_Storage"
set /p "USER_STORAGE=Enter custom storage path for CCTV footage [%DEFAULT_STORAGE%]: "
if "%USER_STORAGE%"=="" set "USER_STORAGE=%DEFAULT_STORAGE%"

echo [+] Configured Customer Storage Path: %USER_STORAGE%
if not exist "%USER_STORAGE%\snapshots" mkdir "%USER_STORAGE%\snapshots"
if not exist "%USER_STORAGE%\recordings" mkdir "%USER_STORAGE%\recordings"
if not exist "%USER_STORAGE%\audit" mkdir "%USER_STORAGE%\audit"

echo.
echo [2/6] DEPLOYING PRODUCTION BINARY FILES TO %INSTALL_DIR%...
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
xcopy /E /I /Y /Q "%PACKAGE_ROOT%\*" "%INSTALL_DIR%\" >nul 2>&1

echo.
echo [3/6] BINDING STORAGE & CLIENT BRANDING...
if not exist "%INSTALL_DIR%\config" mkdir "%INSTALL_DIR%\config"

(
echo {
echo   "company_name": "SOVEREIGN ENTERPRISE",
echo   "storage_path": "%USER_STORAGE:\=\\%",
echo   "installed_at": %time%,
echo   "platform": "windows"
echo }
) > "%INSTALL_DIR%\config\client_config.json"

echo.
echo [4/6] VALIDATING DEVELOPER LICENSE & HARDWARE BINDING...
cd /d "%INSTALL_DIR%"
python -c "from app.security.hardware_lock import get_cross_platform_hardware_id; from app.engine.license_manager import license_manager; print('[+] Hardware ID:', get_cross_platform_hardware_id()); print('[+] License Info:', license_manager.get_license_info().get('tier_name'))"

echo.
echo [5/6] PROVISIONING WINDOWS SERVICE LAUNCHER...
(
echo @echo off
echo set "VISIONXR_STORAGE_PATH=%USER_STORAGE%"
echo python "%INSTALL_DIR%\app\main.py"
) > "%INSTALL_DIR%\start_service.bat"

echo.
echo [6/6] AUTO-DELETING INSTALLER MEDIA FROM DRIVE...
if exist "%SCRIPT_DIR%..\visionxr-release*.zip" (
    del /f /q "%SCRIPT_DIR%..\visionxr-release*.zip" 2>nul
    echo [+] Installer archive securely deleted from drive.
)

echo.
echo ========================================================================
echo [+] VISIONXR PRODUCTION INSTALLATION COMPLETE!
echo     Storage Directory: %USER_STORAGE%
echo     Web Portal       : http://localhost:8022
echo ========================================================================
pause
