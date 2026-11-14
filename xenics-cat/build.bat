@echo off
chcp 65001 >nul
cd /d "%~dp0"
where dotnet >nul 2>&1 || ( echo .NET SDK 8 이 필요합니다: https://dotnet.microsoft.com/download & start https://dotnet.microsoft.com/download & pause & exit /b 1 )
dotnet build -c Release
if errorlevel 1 ( pause & exit /b 1 )
echo.
echo 완료: bin\Release\net48\XenicsCat.exe
pause
