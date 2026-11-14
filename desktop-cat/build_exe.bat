@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [1/3] 빌드 도구 설치...
python -m pip install -q -r requirements.txt pyinstaller
if errorlevel 1 ( echo 설치 실패. 인터넷을 확인하세요. & pause & exit /b 1 )
echo [2/3] 아이콘 생성...
python make_icon.py
echo [3/3] exe 빌드 중... (몇 분 걸립니다)
python -m PyInstaller --noconfirm --clean --onedir --windowed --name "XenicsCat" --icon cat.ico ^
  --add-data "notices.json;." --add-data "LICENSES.md;." --add-data "cat.png;." ^
  --collect-submodules pynput ^
  --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick --exclude-module PySide6.QtQuickWidgets --exclude-module PySide6.QtPdf ^
  --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets --exclude-module PySide6.QtMultimedia ^
  --exclude-module PySide6.QtOpenGL --exclude-module PySide6.QtNetwork --exclude-module PySide6.QtSvg --exclude-module PySide6.QtDBus ^
  --exclude-module tkinter --exclude-module unittest --exclude-module pydoc ^
  cat.py
if errorlevel 1 ( echo 빌드 실패. 위 메시지를 확인하세요. & pause & exit /b 1 )
echo.
echo 완료! dist\XenicsCat\XenicsCat.exe 가 만들어졌습니다.
echo dist\XenicsCat 폴더를 통째로 압축해서 배포하세요.
pause
