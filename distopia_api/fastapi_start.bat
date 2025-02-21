@echo off
echo Before cd: %cd%

cd /d "D:\DTP\DTP\data\distopia_api"
echo After cd: %cd%

call venv\Scripts\activate.bat
echo Virtual Environment Activated: %VIRTUAL_ENV%

uvicorn main:app --reload
pause
