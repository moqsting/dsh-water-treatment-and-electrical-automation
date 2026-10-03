@echo off
chcp 65001 >nul
rem integration-pack Python launcher: add pydeps to PYTHONPATH, then run system Python
setlocal
set "PACK_ROOT=%~dp0.."
set "PYTHONPATH=%PACK_ROOT%\pydeps;%PYTHONPATH%"
call py -3 %*
exit /b %ERRORLEVEL%
