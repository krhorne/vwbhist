@echo off
REM Optional: copies the task/debug config into .vscode so it also works when the folder (not the .code-workspace) is opened.
cd /d "%~dp0"
if not exist .vscode mkdir .vscode
copy /y vscode_config\*.json .vscode\
echo Done.
pause
