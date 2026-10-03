@echo off
rem =====================================================================
rem  water-treatment-and-electrical-automation - one-click installer
rem  Double-click this file. It will:
rem    1) detect your DSH instance directory (contains skills\ or profiles\)
rem    2) check Python 3.12 (offers winget install if missing)
rem    3) install offline python deps (skipped when already bundled)
rem    4) copy the 11 skills into your DSH instance
rem    5) deploy the sidebar workbench-button plugin
rem    6) create a desktop shortcut for the workbench
rem  Optional: set DRY_RUN=1 to only print what would be executed.
rem =====================================================================
chcp 65001 >nul
setlocal EnableDelayedExpansion
title Install water-treatment-and-electrical-automation
cd /d "%~dp0.."
if not exist "setup\install.ps1" (
  echo [ERROR] setup\install.ps1 not found. Please run this file inside the pack folder.
  pause & exit /b 1
)

echo ==========================================================
echo   water-treatment-and-electrical-automation
echo   DSH integration pack - one-click install
echo ==========================================================
echo.

set "SKILLS=%DSH_HOME%"
if not "%SKILLS%"=="" (
  echo [1/2] DSH_HOME detected: %SKILLS%
  goto :have_skills
)

echo [1/2] DSH_HOME not set. Searching for your DSH instance ...
set "CAND="
set "CNT=0"
for /d %%D in ("%USERPROFILE%\.dsh-packs\*") do (
  if exist "%%D\skills" (
    set /a CNT+=1
    echo      found: %%D
    set "CAND=%%D"
  )
)
if exist "%USERPROFILE%\.dsh\skills" (
  set /a CNT+=1
  echo      found: %USERPROFILE%\.dsh
  if "!CNT!"=="1" set "CAND=%USERPROFILE%\.dsh"
)

if "!CNT!"=="1" (
  set "SKILLS=!CAND!"
  echo     -^> using: !SKILLS!
  goto :have_skills
)
if "!CNT!"=="0" (
  echo     no DSH instance found under %USERPROFILE%
  goto :ask
)
echo     multiple instances found
goto :ask

:ask
echo.
echo   Please type the folder of your DSH instance
echo   (the one that contains a "skills" subfolder), then press Enter.
echo   Example: C:\Users\yourname\.dsh-packs\your-profile
echo.
set /p SKILLS="DSH instance folder: "
if "%SKILLS%"=="" (
  echo [ERROR] empty input. Aborted.
  pause & exit /b 1
)

:have_skills
echo.
echo [2/2] Running installer (python deps - smoke test - skills - shortcut) ...
echo       target skills dir: %SKILLS%\skills
echo.

if "%DRY_RUN%"=="1" (
  echo DRY RUN - command that would execute:
  echo   powershell -NoProfile -ExecutionPolicy Bypass -File "%CD%\setup\install.ps1" -SkillsDir "%SKILLS%"
  pause & exit /b 0
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%CD%\setup\install.ps1" -SkillsDir "%SKILLS%"
echo.
echo ==========================================================
echo   Done. Next steps:
echo     - double-click the desktop shortcut to open the workbench
echo     - in DSH, say:  import the pack automation
echo ==========================================================
pause
endlocal
