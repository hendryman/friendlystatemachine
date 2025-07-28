import logging
from pathlib import Path

import re

from llms import llm
from state_machine.behavior import Behavior, Response
from state_machine.diagrams import save_behavior_diagram
from state_machine.emotion_processor import EmotionProcessor


class Character:

    def __init__(self, scene_manager, display_name, persona_name):
        self.scene_manager  = scene_manager
        self.display_name   = display_name
        self.persona_name   = persona_name
        self.emotion        = "neutral"
        self.observations   = []
        

    def llm_callback(self, dictionary):
        raise NotImplementedError()


    def speech_callback(self, dictionary):
        raise NotImplementedError()



class InteractiveCharacter(Character):

    def __init__(self, scene_manager, display_name, persona_name):
        super().__init__(scene_manager, display_name, persona_name)



class ExternalCharacter(Character):

    def __init__(self, scene_manager, display_name, persona_name):
        super().__init__(scene_manager, display_name, persona_name)



class StateMachineCharacter(Character, Behavior):

    def __init__(self, 
                 scene_manager, 
                 display_name: str,
                 persona_name: str,
                 persona: str,
                 few_shots: str,
                 llm_name: str,
                 behaviour_yaml: dict,
                 behaviour_name:  str,
                 auto_speak: bool,
                 default_overrides = {},
            ):
        
        self.diagram_path = Path(scene_manager.output_path, f"{display_name}_behavior.svg").absolute().__str__()
        Character.__init__(self, scene_manager, display_name, persona_name)  
        self.persona = persona
        self.few_shots = few_shots
        self.emotion = "neutral"
        self.speech_style = "Default"
        self.llm_name = llm_name
        self.prompt_counter = 0

        Behavior.__init__(self, behaviour_name, behaviour_yaml, auto_speak, default_overrides)
        self._llm_callback    = self.llm_callback
        self._speech_callback = self.speech_callback

        self._llm = self.scene_manager.get_llm(llm_name)


    def replace_placeholders(self, text):
        if self.persona:
            text = text.replace("_PERSONA", self.persona)
        if self.few_shots:
            text = text.replace("_FEW_SHOTS", self.few_shots)
        emotion = self.emotion.split("|")[0]
        text = text.replace("_EMOTION_ELIZA", str(emotion))

        text = self.scene_manager.replace_placeholders(text)
        return text


    def get_chat_history(self):
        return self.scene_manager.model.get_chat_history()


    def llm_callback(self, event):
        prompt = event.prompt.get()

        prompt = self.replace_placeholders(prompt)
        prompt += f"\n\n**{self.display_name}:**\n"
        prompt = prompt.strip()
        logging.debug(f"[{self.display_name}] Prompt:\n{'-'*64}\n{prompt}\n{'-'*64}")
        
        # Define the callback to be called after calling the LLM.
        def end_callback(prompt, response, timestamp):
            self.prompt_counter += 1
            original_response = response
            response = re.sub(r'(\*\*\S.+?\*\*)', '', response)
            if original_response != response:
                logging.warning(f"Character | {self.display_name} | Replacements made in response: '{original_response}' -> '{response}'")
            return response

        # Call the LLM using the prompt.
        response = self._llm.call(prompt, 0, end_callback)
        logging.info(f'Character | {self.display_name} | LLM Response: "{response}"')
        
        # log_path = Path(self.scene_manager.output_path, "prompts")
        # log_path.mkdir(parents=True, exist_ok=True)
        # with open(Path(log_path, f"{self.display_name}_{self.scene_manager.current_state.id}_{self.scene_manager.model.prompt_counter}.txt"), "a") as f:
        #     f.write(f"{'_'*5}Prompt{'_'*5}\n{prompt}\n{'_'*5}Response{'_'*5}\n{response}")
        #     self.scene_manager.model.prompt_counter += 1

        log_path = self.scene_manager.save_prompt(self.display_name, prompt, response, self.llm_name, self.prompt_counter)

        if getattr(self.scene_manager, "emotion_processor", None):
            self.scene_manager.emotion_processor.classify_text(response)
            meat_event_args = event.get_meat_event_args()
            meat_event_args = self.scene_manager.emotion_processor.from_meat_event(meat_event_args)
            self.emotion = meat_event_args["emotion"].value + "|" + self.scene_manager.emotion_processor.print_emotion_state()
        else:
            meat_event_args = event.get_meat_event_args()

        self.speech_style = meat_event_args["azure_style"].value
        self.data._responses += [Response(response, meat_event_args, False, log_path)]



    def speech_callback(self, event):
        """Callback used by the doctor state machine for speech generation."""

        text = event.speak.get()
        text = self.replace_placeholders(text)
        # Verbose the spoken line and emotion
        logging.info(f"Character | {self.display_name} | Speaking: {text}")
        if getattr(self.scene_manager, "emotion_processor", None):
            self.scene_manager.emotion_processor.classify_text(text)
            meat_event_args = event.get_meat_event_args()
            meat_event_args = self.scene_manager.emotion_processor.from_meat_event(meat_event_args)
            self.emotion = meat_event_args["emotion"].value + "|" + self.scene_manager.emotion_processor.print_emotion_state()
        else:
            meat_event_args = event.get_meat_event_args()
            
        self.speech_style = meat_event_args["azure_style"].value
        self.data._responses += [Response(text, meat_event_args, True)]

    def meatplay_callback(self, event):
        fake_media = None
        for k, v in self.scene_manager.model.fake_media.items():
            if v['id'] == event.id:
                fake_media = v
                break
        
        if fake_media == None:
            logging.error(f"Character | {self.display_name} | Meatplay '{event.id}' not found in fake media./n{self.scene_manager.model.fake_media}")
            return
        
        text = fake_media['text']
        if getattr(self.scene_manager, "emotion_processor", None):
            self.scene_manager.emotion_processor.classify_text(text)
            meat_event_args = event.get_meat_event_args()
            meat_event_args = self.scene_manager.emotion_processor.from_meat_event(meat_event_args)
            self.emotion = meat_event_args["emotion"].value + "|" + self.scene_manager.emotion_processor.print_emotion_state()
        else:
            meat_event_args = event.get_meat_event_args()

        meat_event_args['id'] = event.id
        logging.info(f"Character | {self.display_name} | Meatplay '{event.id}' with text '{text}'")
        self.data._responses += [Response(text, meat_event_args, True)]


    def meatstate_callback(self, event):
        """Callback used by the doctor state machine for meatstate generation."""
        logging.info(f"Character | {self.display_name} | Meatstate '{event.meatstate}'")
        self.scene_manager.add_meatstate(self.display_name, self.persona_name, event.meatstate)


    def before_transition(self, event, state):
        logging.debug(f"Character | {self.display_name} |  Before '{event}', on the '{state.id}' state.")
        return "before_transition_return"


    def on_transition(self, event, state):
        logging.debug(f"Character | {self.display_name} | On '{event}', on the '{state.id}' state.")
        return "on_transition_return"


    def on_exit_state(self, event, state):
        logging.debug(f"Character | {self.display_name} |  Exiting '{state.id}' state from '{event}' event.")


    def on_enter_state(self, event, state):
        logging.info(f"Character | {self.display_name} | Entering '{state.id}' state from '{event}' event.")
        # save_behavior_diagram(self, self.diagram_path)


    def after_transition(self, event, state):
        logging.debug(f"Character | {self.display_name} | After '{event}', on the '{state.id}' state.")
        