# Friendly Fire State Machine

State Machine for scenes in Friendly Fire. Please jump straight to [Guides](docs/) if you are interested in changing scene and behavior scripts.

# Contents

- [Requirements](#requirements)
- [Introduction](#introduction)
  - [Quick Start](#quick-start)
  - [Modes](#modes)
    - [Test](#test)
    - [Perform](#perform)
    - [Simulation](#simulation)
  - [Output](#output)
  - [Options](#options)
- [Guides](docs/)
    - [Behaviors](docs/BEHAVIORS.md)




# Requirements


## Python

Setup a virtual environment and install the requirements. The two key files should be present in the root directory: `openai.key` and `x.key`.

Windows:
```
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

Unix:
```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```



## Ollama
RUN OLLAMA MODEL:

```
ollama run llama3.1:8b
```

# Introduction

## Quick Start

First export the API keys and activate the virtual environment.

Unix:
```bash
export OPENAI_API_KEY=$(cat openai.key)
export XAI_API_KEY=$(cat x.key)

source venv_linux/bin/activate
```

Windows:
```bat
set /p OPENAI_API_KEY=<openai.key
set /p XAI_API_KEY=<x.key

.\venv_windows\Scripts\activate
```

Run the program in test mode.

```
python run_friendly.py --mode=test  --script_dir=scripts/friendly-fires
```

`script_dir` is the path to the script directory. For more information on the script directory, see the [Scene Manager](docs/SCENEMANAGER.md) documentation.

Open the browser to `http://localhost:5000` and start interacting with the program.


## Modes

There are three modes: `test`, `perform`, and `simulation`. In each mode, the program will start a server and open the browser to `http://localhost:5000`. 

### `test`

```
python run_friendly.py --mode=test 
```

This will run the program in test mode. You can interact with the program via the chat inerface in this mode.

If you wish to start at a specific scene, use the `--start_scene` option.

```
python run_friendly.py --mode=test --start_scene=s_tells_dream
```

If you wish to use the message hub in order to receive text from the av-processor, use the `--use_hub` option.

```
python.exe .\run_friendly.py --mode=test --use_hub
```

If you also wish to use the mask, also use the `--wait_for_speak_callback` option.

```
python.exe .\run_friendly.py --mode=test --use_hub --wait_for_speak_callback
```


### `perform`

```
python run_friendly.py --mode=perform
```

This will run the program in performance mode, and it will communicate with the other components (e.g., `audio-visual-processor`, `friendly-touch`) via the message hub.


### `simulation`

```
python run_friendly.py --mode=simulation
```

This will run the program in automatic mode with a bot for the patient. You still need to open the browser to `http://localhost:5000` and manually trigger the first scene.

To change the user persona, use the `--user` option.
To change the user behavior, use the `--user_behaviour` option.


```
python run_friendly.py --mode=simulation --user=Patient --user_behaviour=b_test_0
```

## Output

Each time the scene manager is restarted it will generate a new output directory. The output directory will be named `output/[perform|test|simulation]/[timestamp]`, where `[timestamp]` is the current time in the format `YYYYMMDD-HHMMSS`.

## Options


To see the options, run the help command:

```
python .\run_friendly.py --help
```
Output:

```                     
usage: run_friendly.py [-h] [--mode {simulation,test,perform}] [--output_root OUTPUT_ROOT] [--script_dir SCRIPT_DIR] [--user USER] [--user_behaviour USER_BEHAVIOUR] [--log LOG] [--start_scene START_SCENE]
                       [--server_name SERVER_NAME] [--llm_name LLM_NAME] [--few_shots FEW_SHOTS] [--patient_data_path PATIENT_DATA_PATH]

Run the friendly bot

options:
  -h, --help            show this help message and exit
  --mode {simulation,test,perform}
                        Mode of operation
  --output_root OUTPUT_ROOT
                        Output directory root
  --script_dir SCRIPT_DIR
                        Path to the script directory
  --user USER           User name
  --user_behaviour USER_BEHAVIOUR
                        User behaviour name in simulation mode
  --log LOG             Log level
  --start_scene START_SCENE
                        Start scene
  --server_name SERVER_NAME
                        Server hostname and port
  --llm_name LLM_NAME   LLM name for simulation
  --few_shots FEW_SHOTS
                        Name of few-shots prompts
  --patient_data_path PATIENT_DATA_PATH
                        Path to patient persona
```


# Typeform client

The code in `typeform_client` and the executable `run_typeform.py` allow to connect to the Typeform 

## Running the server

Please check file `typeform_client/typeform_config.yaml` for the form ID, user token and URL of the Typeform GET access point, as well as all the fields, and check the Word file and HTML page in `typeform_client/templates` which are used to generate the consent forms.

```
python .\run_typeform.py --help
```

The client checks Typeform every 1s. Whenever a new form entry is sent on the Typeform service, the client retrieves it, and sends a message to the message hub, and generates a consent form stored in a shared folder. The message is sent on channel `typeform` and contains details about the visitor.


## Options

To see the options, run the help command:

```
python .\run_typeform.py --help
```

Output:

```
usage: run_typeform.py [-h] [--log LOG] [--message_hub MESSAGE_HUB] [--config_yaml_path CONFIG_YAML_PATH] [--template_file TEMPLATE_FILE] [--temporary_file TEMPORARY_FILE] [--path_consent_forms PATH_CONSENT_FORMS] [--location LOCATION]

Run the typeform bot

options:
  -h, --help            show this help message and exit
  --log LOG             Log level
  --message_hub MESSAGE_HUB
                        Message hub hostname and port
  --config_yaml_path CONFIG_YAML_PATH
                        Yaml file with config.
  --template_file TEMPLATE_FILE
                        HTML template for the form.
  --temporary_file TEMPORARY_FILE
                        HTML template for the form.
  --path_consent_forms PATH_CONSENT_FORMS
                        Path where consent forms live.
  --location LOCATION   Location of the installation.
```


# Errata


## Useful Commands

```
ls output/perform/*/chat_history.txt | xargs -I {} du -b {} | sort -nr | head -n 10 | awk '{print $2}' | nl -n ln | while read -r number filepath; do cp "$filepath" "./output/examples/chat_history_${number}.txt"; done
```


## Google Cloud

```
ff-logs@friendlyfires.iam.gserviceaccount.com
``` 
