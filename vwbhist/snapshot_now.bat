@echo off
REM Drag a .pVWB file onto this .bat to record a version now (asks for a note).
cd /d "%~dp0"
set /p NOTE=Note for this version (optional): 
python vwbhist.py snapshot "%~1" -m "%NOTE%"
pause
