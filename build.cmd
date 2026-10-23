@echo off
rem Builds the Windows version (see build_windows.ps1 for options), e.g.  build.cmd -NoInstaller
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_windows.ps1" %*
if errorlevel 1 pause
