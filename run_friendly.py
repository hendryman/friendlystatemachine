import argparse
import logging
from pathlib import Path

from llms import llm
from state_machine import scenemanager
from state_machine.flask_app import run_flask
from datetime import datetime
from state_machine.helpers import LoggerUtils

from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description='Run the friendly bot')
    parser.add_argument('--mode', type=str, choices=['simulation', 'test', 'audio', 'perform'], default='simulation', 
                        help='Mode of operation')
    parser.add_argument('--output_root', type=Path, default='output', help='Output directory root')
    parser.add_argument('--script_dir', type=Path, default='scripts/friendly-fires', help='Path to the script directory')

    parser.add_argument('--user_name', type=str, default='Patient', help='User name')
    parser.add_argument('--persona_name', type=str, default='Test Patient', help='Persona name')
    parser.add_argument('--user_behaviour', type=str, default="test_user", help='User behaviour name in simulation mode')

    parser.add_argument('--log', type=str, default='INFO', help='Log level')

    parser.add_argument('--start_scene', type=str, default=None, help='Start scene')
    parser.add_argument('--use_hub', action='store_true', help='Use hub, test mode only')
    parser.add_argument('--wait_for_speak_callback', action='store_true', help='Wait for speak callback, test mode only')

    parser.add_argument('--server_name', type=str, default='127.0.0.1:5050', help='Server hostname and port')

    parser.add_argument('--llm_name', type=str, default=llm.LLM.default_name(), help='LLM name for simulation')
    parser.add_argument('--few_shots', type=str, default='', help='Name of few-shots prompts')

    parser.add_argument("--use_emotions", action='store_true', help='Bypass emotions system')

    parser.add_argument('--exit_on_complete', action='store_true', help='Exit on completion')
    parser.add_argument('--auto_think', action='store_true', help='Auto Think')
    
    parser.add_argument('--patient_data_path', type=Path, default="data/patient_template_examples/patient_template-hans.json", help='Path to patient persona')

    return parser.parse_args()

def setup_logging(output_path):
    FORMAT = '%(asctime)s %(levelname)s: %(message)s [%(filename)s:%(lineno)s]'
    # logging.basicConfig(format=FORMAT, level="INFO")

    log_file = Path(output_path, "friendly-bot.log")

    # If no filehandler attached
    if not any(isinstance(handler, logging.FileHandler) for handler in logging.getLogger().handlers):
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(FORMAT))
        logging.getLogger().addHandler(file_handler)
    # Update path if different
    else:
        for handler in logging.getLogger().handlers:
            if isinstance(handler, logging.FileHandler):
                handler.baseFilename = log_file

                
def get_output_path(output_root):
    uid = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_path = Path(output_root, uid)
    output_path.mkdir(parents=True, exist_ok=True)
    logging.info(f"Output path: {output_path}")
    return output_path

def get_simulation_scene_manager(mode, **kwargs):
    output_path = get_output_path(kwargs['output_root'])
    setup_logging(output_path)
    logging.info("Running in '{}' mode\n{}\n{}".format('simulation', LoggerUtils.pretty_format_args(kwargs), LoggerUtils.HR))

    model = scenemanager.SceneManagerData()

    kwargs['use_hub'] = False
    kwargs['wait_for_speak_callback'] = False
    kwargs['auto_speak'] = True
    kwargs['mode'] = mode
    kwargs['output_path'] = output_path
    sm = scenemanager.get_scene_manager(model, **kwargs)
    sm.add_bot_user(kwargs['user_name'], kwargs['persona_name'], kwargs['user_behaviour'], kwargs['llm_name'], kwargs['few_shots'])
    return sm

def get_scene_manager_test(**kwargs):
    output_path = get_output_path(kwargs['output_root'])
    setup_logging(output_path)
    logging.info("Running in '{}' mode\n{}\n{}".format('test', LoggerUtils.pretty_format_args(kwargs), LoggerUtils.HR))

    model = scenemanager.SceneManagerData()

    kwargs['output_path'] = output_path
    kwargs['mode'] = 'test'
    sm = scenemanager.get_scene_manager(model, **kwargs)
    sm.add_web_user(kwargs['user_name'], kwargs['persona_name'])
    return sm

def get_scene_manager_perform(**kwargs):
    output_path = get_output_path(kwargs['output_root'])
    setup_logging(output_path)

    logging.info("Running in '{}' mode\n{}\n{}".format('perform', LoggerUtils.pretty_format_args(kwargs), LoggerUtils.HR))
    model = scenemanager.SceneManagerData()
    
    kwargs['use_hub'] = True
    kwargs['wait_for_speak_callback'] = True
    kwargs['mode'] = 'perform'
    kwargs['output_path'] = output_path
    sm = scenemanager.get_scene_manager( model, **kwargs)
    sm.add_web_user(kwargs['user_name'], kwargs['persona_name'])
    return sm
    

def main():
    args = parse_args()
    
    FORMAT = '%(asctime)s %(levelname)s: %(message)s [%(filename)s:%(lineno)s]'
    logging.basicConfig(format=FORMAT, level=args.log)


    args = dict(args._get_kwargs())
    if args['mode'] == 'simulation':
        run_flask(get_simulation_scene_manager, **args)
    elif args['mode'] == 'test':
        run_flask(get_scene_manager_test, **args)
    elif args['mode'] == 'perform':
        run_flask(get_scene_manager_perform, **args)


if __name__ == "__main__":
    main()

