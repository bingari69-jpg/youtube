@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [1/3] Python 확인 중...
python --version >nul 2>&1
if errorlevel 1 (
  echo Python이 없습니다. https://www.python.org/downloads/ 에서 설치할 때 "Add python.exe to PATH" 를 꼭 체크하세요.
  start https://www.python.org/downloads/
  pause
  exit /b 1
)
echo [2/3] 필요한 패키지 설치 중... (처음 한 번만 오래 걸립니다)
python -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo 패키지 설치에 실패했습니다. 인터넷 연결을 확인하세요.
  pause
  exit /b 1
)
echo [3/3] 고양이 실행!
rem 대화 기능을 쓰려면 아래 줄의 rem 을 지우고 키를 넣으세요.
rem set ANTHROPIC_API_KEY=sk-ant-...
start "" pythonw cat.py
exit
