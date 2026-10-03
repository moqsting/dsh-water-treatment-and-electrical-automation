@echo off
rem ============================================================
rem  water-treatment-and-electrical-automation - workbench
rem  Console mode: server log is shown below.
rem  Close this window (or press Ctrl+C) to stop the service.
rem  Recommended: double-click the desktop shortcut instead.
rem ============================================================
chcp 65001 >nul
setlocal
title water-treatment-and-electrical-automation workbench
echo ==========================================================
echo   water-treatment-and-electrical-automation workbench
echo ==========================================================
echo   The browser will open automatically.
echo   Close this window to stop the service.
echo.
py -3 "%~dp0server.py" --open
endlocal
