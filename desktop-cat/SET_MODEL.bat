@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 사용할 모델 이름을 입력하세요. 예: claude-sonnet-5-5  claude-haiku-5-5  claude-opus-5-5
set /p CATMODEL=모델: 
if defined CATMODEL (
  >model.txt echo %CATMODEL%
  echo 저장했습니다. 고양이를 껐다가 다시 켜세요.
) else (
  echo 입력이 없어 바꾸지 않았습니다.
)
pause
