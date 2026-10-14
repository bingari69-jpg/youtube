@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -m pip install -r requirements.txt
echo.
echo 설치 완료. 실행.bat 을 더블클릭하세요.
pause
