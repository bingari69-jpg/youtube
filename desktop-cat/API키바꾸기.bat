@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 새 API 키를 붙여넣고 Enter 를 누르세요.
set /p CATKEY=API 키: 
if defined CATKEY (
  >api_key.txt echo %CATKEY%
  echo 저장했습니다. 고양이를 껐다가 다시 켜세요.
) else (
  echo 입력이 없어 바꾸지 않았습니다.
)
pause
