@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem 대화 기능을 쓰려면 아래 줄의 rem 을 지우고 키를 넣으세요.
rem set ANTHROPIC_API_KEY=sk-ant-...
start "" pythonw cat.py
