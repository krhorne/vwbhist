@echo off
REM Drag a .pVWB file onto this .bat to see what changed in its last saved version.
cd /d "%~dp0"
python vwbhist.py diff "%~1"
pause
