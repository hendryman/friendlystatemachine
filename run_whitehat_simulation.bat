@echo off

set /p OPENAI_API_KEY=<openai.key
set /p XAI_API_KEY=<x.key
set /p OPENROUTER_API_KEY=<openrouter.key

cls

.\venv_win\Scripts\python.exe .\run_friendly.py ^
    --mode=simulation ^
    --script_dir=scripts/friendly-fires ^
    --user_behaviour=test_user_whitehat ^
    --persona_name="Test Patient Whitehat"    

pause
