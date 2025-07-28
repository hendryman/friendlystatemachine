import re
from collections import defaultdict
import logging
from pathlib import Path
import yaml
import uuid 
from state_machine.helpers import LoggerUtils

def load_scenes(script_dir, start_scene, behaviours, personas, few_shots, default_condition=None):
    scene_dir      = Path(script_dir, "scenes")
    logging.info(f"Loading scenes from '{scene_dir}'\n{LoggerUtils.HR}")

    name_expr = re.compile(r"^(\d+[\.\d+]+)\_(.*)$")

    state_defs      = {}
    transition_defs = defaultdict(list)
    automatic_defs  = []

    if not default_condition:
        default_condition = "wait_for_manual"

    scenes = {}
    candidates = list(Path(scene_dir).glob('*.yaml'))
    if not candidates:
        logging.error(f"No scenes found in '{scene_dir}'")
        exit(1)

    for scene_yaml_path in candidates:
        try:
            with open(scene_yaml_path, "r", encoding="utf-8") as f:
                try:
                    scene_data = yaml.safe_load(f)
                except yaml.parser.ParserError as e:
                    logging.error(f"Error parsing scene '{scene_yaml_path}': {e}")
                    exit(1)
                

            match = name_expr.match(scene_yaml_path.stem)
            scene_name  = match.group(2)
            state_index = match.group(1)
            scenes[scene_name] = (scene_yaml_path, scene_data)
        except Exception as e:
            logging.error(f"Error loading scene '{scene_yaml_path}': {e}")
            raise e
        
    logging.info(f"Found {len(scenes)} scenes")


    def get_subgraph(start_scene, scenes, filtered_scenes):
        if start_scene not in scenes:
            logging.error(f"Start scene '{start_scene}' not found")
            exit(1)
        filtered_scenes[start_scene] = scenes[start_scene]
        if 'exits' in scenes[start_scene][1]:
            for transition in scenes[start_scene][1]['exits']:
                target = transition['target']
                if target not in filtered_scenes:
                    get_subgraph(target, scenes, filtered_scenes)

        return filtered_scenes


    if start_scene:

        logging.info(f"Filtering scenes from '{start_scene}'")
        filtered_scenes = {}
        filtered_scenes = get_subgraph(start_scene, scenes, filtered_scenes)
        # scenes[start_scene][1]['scene']['initial'] = True
        

        if "s_PREROLL_init" not in filtered_scenes:
            filtered_scenes["s_PREROLL_init"] = scenes["s_PREROLL_init"]
            filtered_scenes["s_PREROLL_init"][1]['exits'] = [{"condition": None, "target": start_scene}]

        for s in ['s_unknown_fault']:
            if s not in filtered_scenes:
                filtered_scenes[s] = scenes[s]

        scenes = filtered_scenes


    logging.info(f"Generating state machine from {len(scenes)} scenes\n{LoggerUtils.HR}")

    for scene_name, (scene_yaml_path, scene_data) in scenes.items():
        logging.info(f"Loading scene '{scene_name}' from '{scene_yaml_path}'")

        scene = scene_data['scene']

        if 'characters' in scene_data:
            characters = scene_data['characters']
            for character in characters:
                if 'display_name' not in character:
                    logging.warning(f"Character missing display_name")
                    character['display_name'] = uuid.uuid4().hex

                if 'persona_name' not in character:
                    logging.warning(f"Character missing persona_name")
                    character['persona_name'] = ""
                else:
                    if character['persona_name'] not in personas:
                        logging.warning(f"Character '{character['persona_name']}' not defined in personas")
                    
                if 'behavior' not in character:
                    logging.error(f"Character missing behavior")
                    exit(1)
                    
                if character['behavior'] not in behaviours:
                    logging.error(f"Invalid behavior '{character['behavior']}'")
                    exit(1)

                if 'few_shots' in character and character['few_shots'] not in few_shots:
                    logging.warning(f"Invalid few-shots '{character['few_shots']}'")
        else:
            characters = []

        if 'internal_callbacks' in scene_data['scene']:
            internal_callbacks = scene_data['scene']['internal_callbacks']
        else:
            internal_callbacks = []


        playback = False    
        if 'playback' in scene_data:
            assert isinstance(scene_data['playback'], dict), f"Invalid playback value '{scene_data['playback']}'"
            assert set(scene_data['playback'].keys()) == set([1,2,3])
            playback = scene_data['playback']

        state_defs[scene_name] = {
            "meta"   : scene,
            "initial": scene.get('initial', False),
            "final"  : scene.get('final', False),
            "force_mute"        : scene.get('force_mute', False),
            "file_path"         : scene_yaml_path,
            "characters"        : characters,
            "internal_callbacks": internal_callbacks,
            "playback"          : playback,
            "auto_think"        : scene.get('auto_think', None),
        }

        if scene_name not in ["s_PREROLL_init", "s_unknown_fault", "s_FINAL"]:
            transition_name = f"manual_fault"
            transition_defs[transition_name].append( {
                "source"   : scene_name,
                "condition": None,
                "target"   : "s_unknown_fault",
            })

        # if scene_name == "s_unknown_fault":
        #     for scene_name, (scene_yaml_path, scene_data) in scenes.items():
        #     scene['exits'] = [{"condition": "None", "target": start_scene}]

        if 'exits' in scene_data:
            if scene['final'] == True:
                logging.error(f"Scene '{scene_name}' is final and has exits\n{scene_yaml_path}")
                logging.error(f"{scene}")
                exit(1)

            transitions = scene_data['exits']
            for transition in transitions:
                conditions = transition['condition']

                target     = transition['target']
                if target not in scenes.keys():
                    logging.error(f"Invalid target '{target}' in scene '{scene_name}'\n{scene_yaml_path}")
                    exit(1)

                automatic_defs.append( {
                    "source"   : scene_name,
                    "condition": conditions if conditions else default_condition,
                    "target"   : target,
                })

                transition_name = f"manual_{target}"
                transition_defs[transition_name].append( {
                    "source"   : scene_name,
                    "condition": None,
                    "target"   : target,
                })




    logging.info(f"Loaded {len(state_defs)} states\n{LoggerUtils.HR}")
    return state_defs, transition_defs, automatic_defs

