@echo off
REM ---- edit this to the folder where your workbenches are saved ----
set WB_FOLDER=C:\Workbenches
REM -------------------------------------------------------------------
cd /d "%~dp0"
python vwbhist.py watch "%WB_FOLDER%" --interval 10
pause
