#!/bin/bash

export OPENAI_API_KEY=$(cat openai.key)
export XAI_API_KEY=$(cat x.key)
export OPENROUTER_API_KEY=$(cat openrouter.key)

source venv_linux/bin/activate

clear
# python -m messagehub --use_osc_mirror &> ./message-hub.log &
# sleep 2

python run_friendly.py --mode=simulation
# python run_friendly.py --mode=test

read -p "Press any key to continue..."
