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
if not exist api_key.txt (
  echo.
  echo 고양이와 대화하려면 Anthropic API 키가 필요합니다.
  echo 키를 붙여넣고 Enter 를 누르세요. 없으면 그냥 Enter. ^(나중에 api_key.txt 파일을 만들어도 됩니다^)
  set /p CATKEY=API 키: 
  if defined CATKEY (
    >api_key.txt echo %CATKEY%
    echo 저장했습니다: api_key.txt
  )
)
echo [3/3] 고양이 실행!
start "" pythonw cat.py
exit
