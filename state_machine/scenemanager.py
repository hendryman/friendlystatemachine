import yaml
from pathlib import Path
import logging
from datetime import datetime, timedelta
import queue

import json
import random
from statemachine import StateMachine, State

import re
from statemachine.exceptions import TransitionNotAllowed
from state_machine.messagehub import MessageHubClient, format_meat_message, format_meat_meatstate, format_meat_audioplayback
from state_machine.helpers import LoggerUtils

from llms import llm
from .behavior import Behavior
from .character import StateMachineCharacter, ExternalCharacter
from .diagrams import save_sm_diagram
from .emotion_processor import EmotionProcessor
from .helpers import PerformanceMetrics
from .scene_loader import load_scenes
import threading

MEATBOT_NAME = "Dr. Stanley"
client = None

def format_prompt(name, prompt, response, llm_name):
    text = ""
    text += f"{'_'*5}LLM{'_'*5}\n{llm_name}\n"
    text += f"{'_'*5}Prompt{'_'*5}\n{prompt}\n"
    text += f"{'_'*5}Response{'_'*5}\n{response}"
    text = text.encode('utf-8', errors="replace").decode('utf-8')
    return text
        

def get_scene_manager(model, output_path, script_dir, start_scene, **kwargs):
    logging.info(f"Creating Scene Manager with script {script_dir}\n{LoggerUtils.HR}")

    behaviors_dir  = Path(script_dir, "behaviors")
    behavior_paths = { p.stem : p for p in Path(behaviors_dir).glob('*.yaml')}

    persona_dir    = Path(script_dir, "persona")
    persona_dict   = { p.stem : open(p, "r", encoding="utf-8").read()  for p in Path(persona_dir).glob('*.txt')}
    
    few_shots_dir  = Path(script_dir, "few-shots")
    few_shots_dict = { p.stem : open(p, "r", encoding="utf-8").read()  for p in Path(few_shots_dir).glob('*.txt')}

    script_name = Path(script_dir).stem

    behaviour_yamls = {}
    logging.info(f"Validating behaviors\n{LoggerUtils.HR}")
    for bname, bpath in behavior_paths.items():
        name = Path(bpath).stem
        with open(bpath, 'r', encoding="utf-8") as f:
            _yaml_str = f.read()
            try:
                _yaml = yaml.safe_load(_yaml_str)
            except yaml.YAMLError as e:
                logging.error(f"Error parsing YAML file {bpath}: {e}")
                raise e
        Behavior(name, _yaml)

        behaviour_yamls[bname] = _yaml

    logging.info(f"Validated {len(behavior_paths)} behaviors\n{LoggerUtils.HR}")


    state_defs, transition_defs, automatic_defs = load_scenes(
        script_dir, 
        start_scene,
        list(behavior_paths.keys()),
        list(persona_dict.keys()),
        list(few_shots_dict.keys()),
        default_condition= "complete" if kwargs['mode'] == "simulation" else None
    )

    states, scene_params = {}, {}
    transitions = {}
    for sname, params in state_defs.items():
        assert sname not in states, f"State '{sname}' already defined"
        states[sname] = State(name=sname, initial=params['initial'], final=params['final'])

        if not states[sname].final:
            states[sname].to.itself(internal=True, event="internal_update", on="_on_update")

        scene_params[sname] = {
            'meta': params['meta'],
            'auto_think': params['auto_think'],
            'force_mute': params['force_mute'],
            'file_path' : params['file_path'],
            'characters': params['characters'],
            'internal_callbacks': params['internal_callbacks']
        }


    for tname, params_list in transition_defs.items():
        
        for params in params_list:
            try:
                source     = states[params['source']]
                target     = states[params['target']]
                conditions = params['condition']
                assert(source and target), f"Invalid source or target for transition"
                if tname not in transitions:
                    transitions[tname] = source.to(target, cond=conditions)
                else:
                    transitions[tname] |= source.to(target, cond=conditions)
            except Exception as e:
                logging.error(f"Error creating transition '{tname}': {e}")


    for params in automatic_defs:
        source     = states[params['source']]
        target     = states[params['target']]
        conditions = params['condition']
        assert(source and target), f"Invalid source or target for automatic transition"
        source.to(target, cond=conditions, event="e_automatic")
    

    custom_prompts = {}
    for custom_prompt in Path(script_dir, "set-prompts").glob("prompt_*.yaml"):
        with open(custom_prompt, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            custom_prompts[data['name']] = data

    try:
        with open(Path(script_dir, "fake_texts", "static_fake_texts.json"), "r", encoding="utf-8") as f:
            static_fake_texts  = json.loads(f.read())
    except FileNotFoundError as e:
        static_fake_texts = {}
    
    try:
        with open(Path(script_dir, "overrides", "default_overrides.yaml"), "r", encoding="utf-8") as f:
            default_overrides  = yaml.safe_load(f)
    except FileNotFoundError as e:
        default_overrides = {}


    placeholders = {}       
    try:
        for placeholder in Path(script_dir, "placeholders").glob("*.txt"):
            placeholders["_" + placeholder.stem] = open(placeholder, "r").read()
    except FileNotFoundError as e:
        logging.warning(f"No placeholders found in {script_dir}/placeholders")

    model.fake_media = static_fake_texts

    SceneSM_Type = type("SceneSM", (SceneManager,), {
        **states,
        **transitions,
        "script_name"   : script_name,
        "scene_params"  : scene_params, 
        "persona_dict"  : persona_dict,
        "behavior_paths": behavior_paths,
        "behavior_yamls" : behaviour_yamls,
        "few_shots_dict": few_shots_dict,
        "custom_prompts": custom_prompts,
        "static_fake_texts": static_fake_texts,
        "default_overrides": default_overrides,
        "placeholders"  : placeholders
    })
    return SceneSM_Type(model, Path(output_path).absolute().__str__(), **kwargs)

class Message:
    def __init__(self):
        self.model = {}
    def json(self):
        return self.model

class MessageIn(Message):
    class CMD:
        EVENT   = "event"
        CONFIG  = "config"
        MESSAGE = "chat"
    def __init__(self, message_data):
        super().__init__()
        self.message_data = message_data['data'] if 'data' in message_data else {}
        self.command      = message_data['command']
        assert self.command in [self.CMD.CONFIG, self.CMD.MESSAGE, self.CMD.EVENT], f"Unknown command {self.command}"
    
class CachedInferredValue:

    def __init__(self, func):
        self.func = func
        self.value = None
        self.params = None

    def get(self, params):
        if (params and self.params != params):
            self.params = params
            value = self.func(self.params)
            self.value = value

        return self.value

    def get_cached(self):
        return self.value



class InferredValuesManager():

    def __init__(self, scenemanager, model):
        self.scenemanager = scenemanager
        self.model = model   
        self.prompts = {}
        self.cached_inferred_values = {}

        logging.info(f"Setting up inferred values")
        self.custom_prompts = scenemanager.custom_prompts
        self.fake_media     = scenemanager.static_fake_texts
        self.output_path    = scenemanager.output_path

        for custom_prompts_data in self.custom_prompts.values():

            self.add_inferred_value(**custom_prompts_data)
            method_name = custom_prompts_data['name']
            logging.info(f"Adding inferred value {method_name}")
            setattr(self.model, method_name, lambda method_name=method_name: self.get_inferred_value(method_name))



    def save_prompt(self, name, prompt, response, llm_name):

        log_path = Path(self.output_path, "prompts", name)
        log_path.mkdir(parents=True, exist_ok=True)

        file_path = Path(log_path, f"{name}_{self.model.frames}.txt")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(format_prompt(name, prompt, response, llm_name))

        return log_path

    def get_inferred_value(self, name):
        prompt = self.prompts[name]
        prompt = self.model.replace_placeholders(prompt)
        
        val = self.cached_inferred_values[name].get(prompt)
        if val is not None:
            self.model.inferred_values[name] = val
        else:
            logging.error(f"Error getting inferred value {name}")
        logging.info(f"Got inferred value {name}: {val}")
        return self.model.inferred_values[name]


    # def get_inferred_value_cached(self, name):
    #     self.model.inferred_values[name] = self.cached_inferred_values[name].get_cached()
    #     return self.model.inferred_values[name]


    # def get_all_inferred_values_cached(self):
    #     return {name: self.get_inferred_value_cached(name) for name in self.cached_inferred_values}


    def add_inferred_value(self, name, llm_name, prompt, return_type):
        llm = self.scenemanager.get_llm(llm_name)

        self.prompts[name] = prompt

        def process_prompt(parsed_prompt):
            prompt = parsed_prompt.strip()
            logging.info(f"Processing prompt {name} with LLM {llm_name}")

            def end_callback(prompt, response, timestamp):
                log_file = self.save_prompt(name, prompt, response, llm_name)
                return response
            
            response = llm.call(prompt, 0, end_callback, take_first_line=False)

            if return_type == "bool":
                response = bool(self._parse_response_bool(response))
            elif return_type == "json":
                response = self._parse_response_json(response)
            else:
                pass
            logging.info(f"Response: {response}")
            return response

        self.cached_inferred_values[name] = CachedInferredValue(lambda x: process_prompt(x))


    def _parse_response_json(self, response):
        try:
            response = response.strip('`').replace('json\n', '')
            response = json.loads(response)
            if isinstance(response, list):
                response = response[0]
            elif isinstance(response, dict):
                pass
            else:
                raise Exception(f"Invalid response type {type(response)}")
            
            return response
        except Exception as e:
            logging.error(f"Error parsing response: {e}\n{response}")
            return {}


    def _parse_response_bool(self, response):
        is_true  = re.compile(r"^.*([T|t][R|r][U|u][E|e]).*$")
        is_false = re.compile(r"^.*([F|f][A|a][L|l][S|s][E|e]).*$")
        if is_true.match(response):
            return True
        elif is_false.match(response):
            return False
        else:
            logging.warning(f"Unexpected response: {response}")
            return False



class SceneManagerData:   
    def __init__(self):  

        self.chat_history = []
        self.scene_params = None
        self.bots  = {}
        self.users = {}
        self.last_scene_change = None 
        self.init_time = datetime.now() 
        self.start_time = None
        self.end_time   = None
        self.listening = False
        self.mode      = None

        self.prompt_counter = 0

        self.metrics       = None   
        self.frames = 0
        self.glitch = {
            "active": False,
            "duration": 0.5,
            "start"   : 0.0,
            "end"     : 0.5
        }

        self.svg_version = None

        self.fake_media = {}
        self.custom_prompts = {}
        self.inferred_values = {}
        self.typeform = {}
        
        self.update_typeform()


    @property
    def time_since_last_scene_change(self):
        if self.last_scene_change is None:
            return 0
        return datetime.now() - self.last_scene_change


    def replace_placeholders(self, text):        
        pattern = r'\b_(?<=_)[A-Z_]+\b'
        matches = re.findall(pattern, text)[::-1]
        for match in matches:
            if match == "_DATE":
                text = text.replace("_DATE", datetime.now().strftime("%A, %B %d, %Y"))
            elif match == "_TIME":
                text = text.replace("_TIME", datetime.now().strftime("%H:%M"))
            elif match == "_CHAT_HISTORY":
                text = text.replace("_CHAT_HISTORY", self.get_chat_history())
            elif match == "_CHAT_HISTORY_LAST":
                text = text.replace("_CHAT_HISTORY", self.get_chat_history(limit=10))

            elif match == "_EMOTION_USER":
                text = text.replace("_EMOTION_USER", self.users['Patient'].emotion)
            elif match == "_ISSUE":
                if "derive_issue" in self.inferred_values:
                    issue = self.inferred_values["derive_issue"]
                    text = text.replace("_ISSUE", issue["problem"] if issue else "_ISSUE")

            elif match == "_HALLUCINATION":
                if "derive_hallucination" in self.inferred_values:
                    hallucination = self.inferred_values["derive_hallucination"]
                    text = text.replace("_HALLUCINATION", hallucination["therapist"] if hallucination else "_HALLUCINATION")

            elif match == "_HALLUCINATION_DEEPFAKE":
                if "derive_hallucination" in self.inferred_values:
                    hallucination = self.inferred_values["derive_hallucination"]
                    text = text.replace("_HALLUCINATION_DEEPFAKE", hallucination["deepfake"] if hallucination else "_HALLUCINATION")

            elif match[1:] in self.fake_media:
                text = text.replace(match, self.fake_media[match[1:]]["text"])
            else:
                match_value = None
                for name, v in self.typeform.items():
                    value = v[0]
                    placeholder = v[1]
                    if match == placeholder:
                        match_value = value
                        break
                
                if match_value:
                    text = text.replace(match, match_value)
                else:
                    logging.warning(f"Placeholder {match} not found")

        return text    

    def add_message_to_chat_history(self, display_name, persona_name, message, log_file=None):
        # logging.info(f"Adding message from {display_name} (persona {persona_name}): {message}")
        message = message.encode('utf-8').decode('utf-8')
        message = re.sub(r'(\[\S.+?\])', '', message)
        message = re.sub(r'(\*\*\S.+?\*\*)', '', message)
        self.chat_history.append({
            "line" : len([l for l in self.chat_history if l["type"] == "chat"]),
            "type" : "chat",
            "name": display_name,
            "persona": persona_name,
            "message": message,
            "log_file": log_file.absolute().__str__() if log_file else None
        })

    def add_scene_change_to_chat_history(self, scene, params):
        # logging.info(f"Adding scene change: {scene}")
        self.chat_history.append({
            "type" : "scene-change",
            "scene": scene,
            "meta": params['meta']
        })

    def add_bot_instantiation_to_chat_history(self,  b):
        # logging.info(f"Adding scene change: {scene}")
        self.chat_history.append({
            "type" : "bot-instantiation",
            "name": b.display_name,
            "persona":  b.persona_name,
            "behavior" : b.name
        })

    def add_meatstate_to_chat_history(self, display_name, persona_name, meatstate):
        # logging.info(f"Adding meatstate from {display_name} (persona {persona_name}): {meatstate}")
        self.chat_history.append({
            "type" : "meatstate",
            "name": display_name,
            "persona": persona_name,
            "message": f"MeatState {meatstate}"
        })
        
    def get_chat_history(self, limit=None):
        chat_history = [ c for c in self.chat_history if c["type"] == "chat"]
        srt = 0
        end = len(chat_history)
        if limit:
            srt = max(0, end - limit)

        s = '--- Beginning of transcript ---\n\n'
        for msg in chat_history[srt:end]:
            s += f'**{msg["name"]}:**\n{msg["message"]}\n\n'
        s += '--- End of transcript ---'
        return s  

    # Turn taking
    def user_spoke_last(self):
        chat_history = [ c for c in self.chat_history if c["type"] == "chat"]
        try:
            return chat_history[-1]['name'] in self.users
        except (IndexError, KeyError) as e:
            return False
        
    def bot_spoke_last(self):  
        chat_history = [ c for c in self.chat_history if c["type"] == "chat"]
        try:
            return chat_history[-1]['name'] in self.bots
        except (IndexError, KeyError) as e:
            return False
        
    def no_waiting_responses(self):
        return not any([len(bot.data._responses) > 0 for bot in self.bots.values()])
    
    def bot_speaking(self):
        return any([bot.is_speaking() for bot in self.bots.values()])

    def bots_complete(self):
        if len(self.bots) == 0:
            return True
        return all([bot.current_state.id == "s_final" and not bot.is_speaking() for bot in self.bots.values()])

    def complete(self):
        complete = self.bots_complete() 
        return complete           

    # Timeouts
    def timeout(self, T):
        return self.time_since_last_scene_change > timedelta(seconds=T)
    
    def timeout_2(self):
        return self.timeout(2)
        
    def timeout_3(self):
        return self.timeout(3)
    
    def timeout_exit(self):
        return self.timeout(10)
    
    def timeout_preroll(self):
        return self.timeout(7)

    def short_timeout(self):
        return self.timeout(30)
    
    def tiny_timeout(self):
        return self.timeout(1)
    
    def long_timeout(self):
        return self.timeout(45)
    
    # Custom prompts

    def update_typeform(self):
        try:
            with open("output/typeform.json") as f:
                self.typeform = json.loads(f.read())
                logging.info("Loaded typeform information: %s", self.typeform)
        except:
            logging.warning("Cannot read typeform data.")


    def update_fake_texts(self):
        def update_fake_texts_task():
            self.derive_issue()
            hallucination = self.derive_hallucination()
        
            if 'HALLUCINATION' not in self.fake_media and "deepfake" in hallucination:
                self.fake_media['HALLUCINATION'] = {
                    "id": 401,
                    "text": hallucination["deepfake"],
                    "audio": "user",
                    "video": "user"
                }
                logging.info(f"Updating fake texts: {hallucination}")
            else:
                logging.error(f"Error updating fake texts: {hallucination}")

        update_thread = threading.Thread(target=update_fake_texts_task)
        update_thread.start()




class SceneManager(StateMachine):
 

    def __init__(self, 
                 model, 
                 output_path,
                 use_hub = False, 
                 auto_speak = False, 
                 wait_for_speak_callback = False, 
                 exit_on_complete = False,
                 exit_callback = None,
                 auto_think = False,
                 use_emotions = False,
                 llm_name = None,
                 *args, **kwargs):
        
        logging.info(f"Creating SceneManager\n{LoggerUtils.HR}")

        self.wait_for_speak_callback = wait_for_speak_callback
        self.use_hub                 = use_hub        
        self.auto_speak              = auto_speak
        self.msg_in                  = queue.Queue()
        self.performance_metrics     = PerformanceMetrics()
        self.output_path             = output_path
        self.exit_on_complete        = exit_on_complete
        self.exit_callback           = exit_callback
        self.auto_think              = auto_think   
        self.use_emotions            = use_emotions
        self.llm_name                = llm_name or llm.LLM.default_name()

        self._llms = {} 

        self.inferred_values_manager = InferredValuesManager(self, model)

        if use_emotions:
            self.emotion_processor = EmotionProcessor()

        if self.wait_for_speak_callback and not self.use_hub:
            raise Exception("Wait for speak callback requires MessageHub")
            
        self.diagram_path = Path(self.output_path, "scenemanager.svg").absolute().__str__()
        logging.info(f"Output path: {self.output_path}")

        if use_hub:
            self._setup_message_hub()

        super().__init__(model)
        self.set_listening(False)


    def replace_placeholders(self, text):
        pattern = r'\b_(?<=_)[A-Z_]+\b'
        for _ in range(2):
            matches = re.findall(pattern, text)[::-1]
            for match in matches:
                if match in self.placeholders:
                    text = text.replace(match, self.placeholders[match])

        return self.model.replace_placeholders(text)


    def wait_for_manual(self):
        return False
    
    def get_llm(self, llm_name):
        if llm_name not in self._llms:
            logging.info(f"Creating LLM {llm_name}")
            self._llms[llm_name] = llm.LLM(llm_name)

        return self._llms[llm_name]

    def update(self):
        self.performance_metrics.register_frame_start()
        try:
            self.internal_update()
        except TransitionNotAllowed as e:
            if self.current_state.id != "s_FINAL":
                logging.warning(f"SceneManager | No more transitions available {self.current_state.id}")
        
        try:
            self.e_automatic()
        except TransitionNotAllowed as e:
            logging.debug(f"SceneManager | {e}")

        self.performance_metrics.register_frame_end() 
        self.model.metrics = self.performance_metrics.get_metrics()
        self.model.frames += 1



    def add_bot_user(self, display_name, persona_name, behavior_name, llm_name, few_shots_name):
        persona = self.persona_dict[persona_name] if persona_name in self.persona_dict else None
        few_shots = self.few_shots_dict[few_shots_name] if few_shots_name in self.few_shots_dict else None
        assert(self.auto_speak), "Auto speak must be enabled for bot users"
        logging.info(f"Creating bot user '{display_name}' with persona '{persona_name}', behavior '{behavior_name}', LLM '{llm_name}'")
        
        try:
            behaviour_yaml = self.behavior_yamls[behavior_name]
        except KeyError as e:
            logging.error(f"Behavior '{behavior_name}' not found")
            raise e

        self.model.users[display_name] = StateMachineCharacter(
                    self, 
                    display_name=display_name,
                    persona_name=persona_name,
                    persona=persona,
                    few_shots=few_shots,
                    behaviour_name=behavior_name,
                    behaviour_yaml=behaviour_yaml,
                    llm_name=llm_name,
                    auto_speak=self.auto_speak
        )
        self.model.users[display_name].e_init()


    def add_web_user(self, display_name, persona_name):
        self.model.users[display_name] = ExternalCharacter(self, display_name, persona_name)


    def add_meatstate(self, display_name, persona_name, meatstate):
        global client
        if display_name in self.model.bots:
            bot = self.model.bots[display_name]

            self.model.add_meatstate_to_chat_history(display_name, persona_name, meatstate)

            if bot.pending_responses():
                self._speakBot(bot)
            else:
                if bot.current_state.id == "s_stop":
                    self._advanceBot(bot)

            # self._advanceUsers()
            
            if display_name == MEATBOT_NAME and client:
                logging.info(f"Sending meat message {display_name} (persona {persona_name}): {meatstate}")
                data = format_meat_meatstate(meatstate)
                client.send_message("meat-command", data)

        else:
            logging.warning(f"Unknown character '{display_name}'")

        self.save_chat_history()


    def add_message(self, display_name, persona_name, message, emotion_args = None, external=False, log_file=None): 
        global client
        logging.debug(f"Processing message from {display_name} (persona {persona_name}): {message}")
        if display_name in self.model.users:
            user = self.model.users[display_name]
            self.model.add_message_to_chat_history(display_name, persona_name, message, log_file=log_file)
            
            if type(user) == StateMachineCharacter:
                user.data._speaking = False
            
            auto_think = self.model.scene_params['auto_think']
            auto_think = auto_think if auto_think is not None else self.auto_think

            if auto_think and not self.model.bot_speaking():
                self.add_meatstate(MEATBOT_NAME , MEATBOT_NAME , "think")
                
            self._advanceBots()
                
        elif display_name in self.model.bots:
            bot = self.model.bots[display_name]

            if not self.wait_for_speak_callback or external or display_name != MEATBOT_NAME :
                bot.data._speaking = False
                self.set_listening(True)
                self.model.add_message_to_chat_history(display_name, persona_name, message)

                if bot.pending_responses():
                    self._speakBot(bot)
                else:
                    if bot.current_state.id == "s_stop":
                        self._advanceBot(bot)
                    else:
                        self._advanceUsers()

            else:
                if client and display_name == MEATBOT_NAME :
                    self.set_listening(False)
                    logging.info(f"Sending meat message {display_name} (persona {persona_name}): {message}")

                    if getattr(self, "emotion_processor", None):
                        emotion_args = self.emotion_processor.overwrite_with_emotion_state(emotion_args)


                    channel = emotion_args.pop('channel', None)
                    if channel == "say": 
                        data = format_meat_message(message, **emotion_args)
                    elif channel == "play":
                        data = format_meat_audioplayback(message, **emotion_args)
                    else:
                        raise Exception(f"Unknown channel {emotion_args['channel']}")
                    
                    client.send_message("meat-command", data)
                else:
                    if self.use_hub:
                        raise Exception("MessageHub not enabled")

        else:
            logging.warning(f"Unknown character '{display_name}'")

        self.save_chat_history()


    def save_chat_history(self):
        path = Path(self.output_path, "chat_history.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(self._get_pretty_chat_history())


    def save_prompt(self, name, prompt, response, llm_name, prompt_counter):
        
        log_path = Path(self.output_path, "prompts", name)
        log_path.mkdir(parents=True, exist_ok=True)
        with open(Path(log_path, f"{name}_{self.model.frames}_{prompt_counter}.txt"), "a", encoding="utf-8") as f:
            text = format_prompt(name, prompt, response, llm_name)
            f.write(text)

        return log_path

    def get_chat_history(self):
        return self.model.get_chat_history()
    
    # def after_enter_state(self, event, state):
    #     for func_name in self.model.scene_params['internal_callbacks']:
    #         func = getattr(self, func_name, None)
    #         if func:
    #             logging.info(f"SceneManager | Running callback '{func_name}'")
    #             func()
    #             continue
    #         else:
    #             func = getattr(self.model, func_name, None)
    #             if func:
    #                 logging.info(f"SceneManager | Running Model callback '{func_name}'")
    #                 func()
    #                 continue
            
    #         logging.warning(f"Unknown callback '{func_name}'")
    #         raise Exception(f"Unknown callback '{func_name}'")

    def on_enter_state(self, event, state):
        srt_time = datetime.now()
        logging.info(f"SceneManager |\n{LoggerUtils.SHR}\n\tScene [{state.id}] from '{event}'\n{LoggerUtils.SHR}")
        self.model.last_scene_change = datetime.now()

        self.model.scene_params = self.scene_params[state.id]

        # logging.info(f"SceneManager | Scene callbacks: {self.model.scene_params['internal_callbacks']}")

        
        self.model.add_scene_change_to_chat_history(state.id, self.model.scene_params)

        self._populate_bots()


        # logging.info(f"SceneManager | Bots: {','.join(self.model.bots.keys())}")
        if not self.model.bot_spoke_last():
            self._advanceBots()

        save_sm_diagram(self, self.diagram_path)
        self.model.svg_version = self.model.last_scene_change.strftime("%Y%m%d-%H%M%S")

        for func_name in self.model.scene_params['internal_callbacks']:
            func = getattr(self, func_name, None)
            if func:
                logging.info(f"SceneManager | Running callback '{func_name}'")
                func()
                continue
            else:
                func = getattr(self.model, func_name, None)
                if func:
                    logging.info(f"SceneManager | Running Model callback '{func_name}'")
                    func()
                    continue
            
            logging.warning(f"Unknown callback '{func_name}'")
            raise Exception(f"Unknown callback '{func_name}'")

        if self.model.state == "s_FINAL":
            self.model.end_time = datetime.now()
            total_time = self.model.end_time - self.model.start_time
            logging.info(f"SceneManager | Total time: {total_time}")
            logging.info(f"SceneManager | Metrics: {self.model.metrics}")
            if self.exit_on_complete and self.exit_callback:
                logging.info(f"SceneManager | Exiting on complete")
                self.exit_callback()


        logging.info(f"Time to enter scene: {datetime.now().__sub__(srt_time).microseconds / 1000} ms")


    def on_exit_state(self, event, state):
        logging.info(f"SceneManager | exiting '{state.id}' state to '{event}'")
        self._stopBots(event)
        self.model.bots = {}

        if self.model.state == "s_PREROLL_init":
            self.model.start_time = datetime.now()


    def _populate_bots(self):
        for character in self.model.scene_params['characters']:
            display_name   = character['display_name']
            persona_name   = character['persona_name']
            behavior_name  = character['behavior']
            persona        = self.persona_dict[persona_name] if persona_name in self.persona_dict else None
            few_shots_name = character['few_shots'] if 'few_shots' in character else ""
            few_shots      = self.few_shots_dict[few_shots_name] if few_shots_name in self.few_shots_dict else None
            llm_name       = character['llm_name'] if 'llm_name' in character else self.llm_name
            logging.info(f"Creating character '{display_name}' with persona '{persona_name}', behavior '{behavior_name}', LLM '{llm_name}'")
            # logging.debug(f"Persona:\n'{persona}'")
            # logging.debug(f"Few-shots:\n'{few_shots}'")

            try:
                behaviour_yaml = self.behavior_yamls[behavior_name]
            except KeyError as e:
                logging.error(f"Behavior '{behavior_name}' not found")
                raise e
            
            assert persona_name not in self.model.bots, f"Bot '{persona_name}' already defined"
            assert persona_name not in self.model.users, f"User '{persona_name}' already defined"
            assert display_name != "Patient", "Patient is a reserved name"
            self.model.bots[display_name] = StateMachineCharacter(
                self,
                display_name=display_name,
                persona_name=persona_name,
                persona=persona,
                few_shots=few_shots,
                llm_name=llm_name,
                behaviour_name=behavior_name,
                behaviour_yaml=behaviour_yaml,
                auto_speak=self.auto_speak,
                default_overrides=self.default_overrides
            )

            self.model.add_bot_instantiation_to_chat_history(self.model.bots[display_name])
            
            self.model.bots[display_name].e_init()


    def _advanceBots(self):
        logging.debug(f"Advancing bots")
        for bot in self.model.bots.values():
            self._advanceBot(bot)


    def _advanceUsers(self):
        logging.debug(f"Advancing users")
        for user in self.model.users.values():
            if( type(user) == StateMachineCharacter):
                logging.info(f"Advancing user {user.display_name}")
                if self.model.no_waiting_responses():
                    self._advanceBot(user)
            if( type(user) == ExternalCharacter):
                pass


    def _speakBots(self):
        for bot in self.model.bots.values():
            self._speakBot(bot)


    def _advanceBot(self, bot):
        try:
            bot.e_advance()
            return True
        except TransitionNotAllowed as e:
            logging.info(f"SceneManager | Can't advance, No transitions available {bot.display_name}")
        return False


    def _speakBot(self, bot):
        try:
            bot.e_speak()
            logging.info(f"Speaking bot {bot.display_name}")
            return True
        except TransitionNotAllowed as e:
            logging.info(f"SceneManager | Can't speak, No more transitions available {bot.display_name}")
        return False
 

    def _stopBots(self, event):
        for bot in self.model.bots.values():
            logging.info(f"Stopping bot {bot.display_name}")
            # event = "end" if event == "e_automatic" else event
            try:
                bot.e_stop(scene_event=event)
            except TransitionNotAllowed as e:
                logging.info(f"SceneManager | no more transitions for {bot.display_name}")

    def _on_update(self):
        self._process_messages()


    def set_listening(self, listening):
        global client

        # if not self.use_hub:
        #     # This is only when there use_hub is False. If we use a hub with speech recognition,
        #     # then the confirmation has to come from hub av-command messages stt-enabled or stt-disabled.
        logging.debug(f"Force mute: {self.model.scene_params['force_mute']}")
        if self.model.scene_params['force_mute']:
            listening = False

        if any([bot.is_speaking() for bot in self.model.bots.values()]):
            listening = False

        self.model.listening = listening
            
        if client:
            client.send_message("av", json.dumps({"av-command": "stt-control", "data": {"listening": listening}}))
            logging.info(f"Set listening to {self.model.listening}")
            # if not self.model.listening:
            #     logging.info(f"Sending think message")
            #     self.add_meatstate(MEATBOT_NAME , MEATBOT_NAME , "think")
        else:
            if self.use_hub:
                raise Exception("MessageHub not enabled")


    def _process_messages(self):

        while not self.msg_in.empty():
            msg = self.msg_in.get()
            assert type(msg) == MessageIn
            logging.info(f"Processing message: {msg.command} {msg.message_data}")
            if msg.command == MessageIn.CMD.MESSAGE:
                if 'user' not in msg.message_data or 'message' not in msg.message_data:
                    logging.warning(f"Missing user or message in chat message")
                    continue

                self.add_message(msg.message_data['user'], msg.message_data['user'], msg.message_data['message'], external=True)

            elif msg.command == MessageIn.CMD.EVENT:
                if 'action' not in msg.message_data:
                    logging.warning(f"Missing action in config message")
                    continue
                
                if msg.message_data['action'] == "transition":
                    transition = msg.message_data['transition']
                    assert transition.startswith("manual_"), f"Invalid transition '{transition}'"
                    logging.info(f"Received transition '{transition}'")
                    self.send(transition)

                elif msg.message_data['action'] == "force_advance":
                    logging.info(f"Received force_advance")
                    self._advanceBots()

                elif msg.message_data['action'] == "microphone":
                    if msg.message_data['listening'] == "toggle":
                        logging.info(f"Received microphone toggle")
                        self.set_listening(not self.model.listening)
                    elif type(msg.message_data['listening']) == bool:
                        self.set_listening(msg.message_data['listening'])
                    else:
                        logging.error(f"Invalid listening value {msg.message_data['listening']}")

                elif msg.message_data['action'] == "speak":
                    self._speakBots()

                elif msg.message_data['action'] == "emotion-recognition":
                    # TODO(piotr) Updated self.emotion_user
                    user_emotion = msg.message_data['message']
                    self.model.users['Patient'].emotion = user_emotion
                    if self.use_emotions:
                        self.emotion_processor.from_user(user_emotion)
                    logging.info(f"User emotion: {user_emotion}")
                    
                elif msg.message_data['action'] == "vision-visitor-attributes":
                    attributes = msg.message_data['message']['data']['attributes']
                    self.model.users['Patient'].observations = attributes


                elif msg.message_data['action'] == "override":
                    name     = msg.message_data['name']
                    override = msg.message_data['override']
                    self.model.bots[name].override(override)
                else:
                    logging.warning(f"Unknown action {msg.message_data['action']}")
                    # raise Exception(f"Unknown action {msg.message_data['action']}")
            else:
                # logging.warning(f"Unknown command {msg.command}")
                raise Exception(f"Unknown command {msg.command}")


    def _setup_message_hub(self):
        global client
        if client:
            logging.warning(f"MessageHub already enabled")
        else:
            client = MessageHubClient("http://127.0.0.1:8005")

        def on_words_in(channel, data):
            logging.info(f"Received words-in message: {data}")
            try:
                data = json.loads(data)
                name = data["entity"]
                text = data["text"]

                if name == "user":
                    self.msg_in.put(MessageIn({
                        "command": MessageIn.CMD.MESSAGE,
                        "data": {
                            "user": "Patient",
                            "message": text
                        }
                    }))
                elif name in self.model.bots or name == MEATBOT_NAME :
                    self.msg_in.put(MessageIn({ 
                        "command": MessageIn.CMD.MESSAGE,
                        "data": {
                            "user": name,
                            "message": text
                        }  
                    })) 
                else:
                    logging.warning(f"Unknown entity '{name}'")

            except Exception as e:
                logging.error(f"Error processing words-in message: {e}")

        def on_av(channel, data):
            try:
                data = json.loads(data)
                name = data["av-command"]
                if name == "emotion-recognition":
                    text = data["data"]["text"]
                    logging.debug(f"Received av message: {data}, {text}")
                    self.msg_in.put(MessageIn({
                        "command": MessageIn.CMD.EVENT,
                        "data": {
                            "action": "emotion-recognition",
                            "message": text
                        }
                    }))
                elif name == "vision-visitor-attributes":
                    logging.info(f"Received vision-visitor-attributes message: {data}")
                    self.msg_in.put(MessageIn({
                        "command": MessageIn.CMD.EVENT,
                        "data": {
                            "action": "vision-visitor-attributes",
                            "message": data
                        }
                    }))
                elif name == "stt-enabled":
                    logging.info("stt-enabled")
                    self.model.listening = True
                elif name == "stt-disabled":
                    logging.info("stt-disabled")
                    self.model.listening = False
                else:
                    pass
                    # logging.warning(f"Unknown av-command '{name}'")
            except Exception as e:
                logging.error(f"Error processing av message: {e}")

        def on_typeform(channel, data):
            try:
                data = json.loads(data)
                data = data["data"]
                first_name = data["first_name"][0]
                last_name = data["last_name"][0]
                year_born = data["year_of_birth"][0]
                residence = data["residence"][0]
                occupation = data["occupation"][0]
                gender = data["gender"][0]
                experience_ai = data["experience_ai"][0]
                area_life = data["area_life"][0]
                process_thoughts_and_feelings = data["process_thoughts_and_feelings"][0]
                logging.info(f"{first_name} {last_name} is {gender} and was born in {year_born} and lives in {residence}.")
                logging.info(f"{first_name}'s occupation is {occupation} and their experience of AI is {experience_ai}.")
                logging.info(f"{first_name} needs help with {area_life} and copes by doing the following: {process_thoughts_and_feelings}.")
            except Exception as e:
                logging.error(f"Error processing av message: {e}")


        if self.use_hub:
            logging.info(f"Setting up callbacks")
            client.set_callback("words-in", on_words_in)
            client.set_callback("av", on_av)
            client.set_callback("typeform", on_typeform)


        if self.wait_for_speak_callback:
            # The on_av callback for emotion recognition is already added because use_hub is True.
            pass

        
        client.send_message("av", json.dumps({"av-command": "stt-control", "data": {"listening": False}}))

    def _get_pretty_chat_history(self):
        messages = []
        for m in self.model.chat_history:
            if m['type'] == 'chat':
                messages += [f"{m['line']:03d} {m['name']}: {m['message']}"]
            elif m['type'] == 'scene-change':
                messages += [f"------{m['scene']}------"]
                messages += [f"{m['meta']}"]                
                messages += [f"------------------------"]
            elif m['type'] == 'meatstate':
                messages += [f"[{m['name']}: {m['message']}]"]
        messages = '\n'.join(messages)
        messages = messages.encode('utf-8', errors="ignore").decode('utf-8')
        return messages
    

