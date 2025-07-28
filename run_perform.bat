@echo off

set /p OPENAI_API_KEY=<openai.key
set /p XAI_API_KEY=<x.key
set /p OPENROUTER_API_KEY=<openrouter.key

cls

@REM wt -p "Command Prompt" -d . cmd /k ".\venv\Scripts\python.exe -m messagehub --use_osc_mirror --meat_host 0.0.0.0"

.\venv_win\Scripts\python.exe .\run_friendly.py --mode=perform 
@REM .\venv_win\Scripts\python.exe .\run_friendly.py --mode=perform --start_scene s_wrongvideo_accusation
pause
