@echo off

set /p OPENAI_API_KEY=<openai.key
set /p XAI_API_KEY=<x.key
set /p OPENROUTER_API_KEY=<openrouter.key

cls

@REM .\venv\Scripts\python.exe .\run_friendly.py --mode=test --script_dir=scripts/tests
.\venv_win\Scripts\python.exe .\run_friendly.py --mode=test 

pause
