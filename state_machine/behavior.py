import logging
from typing import Any

import statemachine
from statemachine import StateMachine, State
from datetime import datetime, timedelta
import yaml
from pathlib import Path


from state_machine.entity import EventClass, DynamicEventsClass


def dummy_speech_callback(event):
  logging.info(event)


def dummy_llm_callback(event):
  logging.info(event)


def dummy_meatstate_callback(event):  
  logging.info(event)
  

def dummy_meatplay_callback(event):
  logging.info(event)

class InitEvents(EventClass):
  def __init__(self, dictionary: dict[str, Any], *args, **kwargs):
    super().__init__("init", dictionary, *args, **kwargs)



class EndEvents(EventClass):
  def __init__(self, dictionaries: dict[str, dict[str, Any]], *args, **kwargs):
    super().__init__("end", dictionaries, *args, **kwargs)


class DynamicEvents(DynamicEventsClass):
  def __init__(self, dictionaries: dict[str, dict[str, Any]], *args, **kwargs):
    kwargs["max_iterations"] = kwargs.pop("max-iterations", -1)
    super().__init__("automatic", dictionaries, *args, **kwargs)



  # def get(self, key: str, counter: int) -> dict[str, str]:
  #   if not isinstance(key, str) or key not in ["manual", "automatic"]:
  #     raise Exception(f"Unknown event {key} for Dynamic state {self.name}")
  #   return super().get(key, counter)

class OverrideEvents(EventClass):
  """Class storing multiple transitions, prompts, sentences to speak and/or emotions of the override state."""
  def __init__(self, dictionaries: dict[str, dict[str, Any]], *args, **kwargs):
    super().__init__("manual", dictionaries, *args, **kwargs)



class Response(object):
  def __init__(self, text, emotion_args, speak_immediate, log_path=None):
    self.text            = text
    self.emotion         = emotion_args
    self.speak_immediate = speak_immediate
    self.log_path        = log_path


  def __str__(self):
    return f"Response: {self.text} - Emotion: {self.emotion} - Speak Immediate: {self.speak_immediate}"



class BehaviorData(object):

  def __init__(self, parent):
    self.parent = parent
    self._events           = []
    self._responses        = [] 
    self._speaking   = False

    self.next_process_time = None
    
    self.speak_counter   = 0
    self.dynamic_counter   = 0
    # self.last_heard_time = 0
    # self.last_speak_time = 0
    self.scene_metadata  = {}
    self.flag_stop       = False
    self.auto_speak      = False
    self.time_start      = datetime.now()

    
  def json(self):
    return {
      "response"       : [str(r.text) for r in self._responses],
      "speaking"       : self._speaking,
      "speak_counter"  : self.speak_counter,
      # "last_heard_time": self.last_heard_time,
      # "last_speak_time": self.last_speak_time,
      "scene_metadata" : self.scene_metadata,
      "auto_speak"     : self.auto_speak,
      "flag_stop"      : self.flag_stop,
      "time_start"     : datetime.strftime(self.time_start, "%Y-%m-%d %H:%M:%S")
      
    }



class Behavior(StateMachine):
  """Class implementing the State Machine for a given Behavior."""

  # States within the Behavior.
  s_init      = State(initial=True)
  s_start     = State()
  s_dynamic   = State()
  s_stop      = State()
  s_final     = State(final=True)

  e_init = s_init.to(s_start)

  e_advance = (
    s_start.to(s_dynamic, cond="not is_speaking")
    | s_dynamic.to(s_dynamic, cond="not is_speaking and !stop_flagged")
    | s_dynamic.to(s_stop, cond="not is_speaking")
    | s_stop.to(s_final, cond="not is_speaking")
  )

  # e_advance = (
  #   s_start.to(s_start, cond="not is_speaking and has_events")
  #   | s_start.to(s_dynamic, cond="not is_speaking")
  #   | s_dynamic.to(s_dynamic, cond="not is_speaking and !stop_flagged")
  #   | s_dynamic.to(s_stop, cond="not is_speaking")
  #   | s_stop.to(s_stop, cond="not is_speaking and has_events")
  #   | s_stop.to(s_final, cond="not is_speaking")
  # )

  e_speak = (
    s_start.to(s_start, cond="not is_speaking and pending_responses")
    | s_dynamic.to(s_dynamic, cond="not is_speaking and pending_responses")
    | s_stop.to(s_stop, cond="not is_speaking and pending_responses")
  )

  e_stop = (
    s_dynamic.to(s_stop, cond="not is_speaking")
  )

  e_final = s_stop.to(s_final, cond="not is_speaking and no_pending_responses")


  def stop_flagged(self):
    return self.data.flag_stop

  def has_events(self):
    return len(self.data._events) > 0

  def is_speaking(self):
    return self.data._speaking


  def no_pending_responses(self):
    return len(self.data._responses) == 0

  def pending_responses(self):
    return len(self.data._responses) > 0

  def __init__(self,
               behaviour_name: str,
               behaviour_yaml: str,
               auto_speak: bool = True,
               default_overrides: dict[str, dict[str, Any]] = {},
               **kwargs):
    
    self.name  = behaviour_name
    self._yaml = behaviour_yaml

    self._speech_callback     = getattr(self, "speech_callback", None)    or dummy_speech_callback
    self._llm_callback        = getattr(self, "llm_callback", None)       or dummy_llm_callback
    self._meatstate_callback  = getattr(self, "meatstate_callback", None) or dummy_meatstate_callback
    self._meatplay_callback   = getattr(self, "meatplay_callback", None)  or dummy_meatplay_callback

    self.data = BehaviorData(self)
    self.data.auto_speak = auto_speak
    try:
      self._import_yaml(default_overrides)
      super(Behavior, self).__init__(allow_event_without_transition=True, **kwargs)
    except Exception as e:
      logging.error(f"Error creating Behavior {self.name}: {e}")
      raise e


  def on_enter_state(self, event, state):
      logging.debug(f"{self.name} | Entering '{state.id}' state from '{event}' event.")


  def on_enter_s_start(self, event, state):
    if event == "e_speak":
      self._process_events()
      self._process_responses()
      return
    
    new_events = self._init.get() if self._init else None 
    if new_events:
      self.data._events += new_events
    self._process_events()
    self._process_responses()


  def on_enter_s_dynamic(self, event, state):
    if event == "e_speak":
      return
    
    new_events = self._dynamics.get("automatic", self.data.dynamic_counter) if self._dynamics else None
    if new_events is None:
      logging.debug(f"Flagging stop in Behavior {self.name}, event {event}")
      self.data.flag_stop = True
    else:
      self.data.dynamic_counter += 1
      self.data._events.append(new_events)

    self._process_events()
    self._process_responses()


  def on_enter_s_stop(self, event, state, scene_event=None):
    if event == "e_speak":
      self._process_events()
      self._process_responses()
      return
    
    scene_event = scene_event if scene_event else "end"
    new_events = self._ends.get(scene_event) if self._ends else None
    if new_events:
      self.data._events += new_events
    self._process_events()
    self._process_responses()


  def on_e_speak(self, event, state):
    self.data.last_speak_time = datetime.now()
    response = self.data._responses.pop(0)
    self.data.speak_counter += 1
    self.data._speaking = True
    logging.info(f'{self.name} | Speaking: "{response.text}"')
    self.scene_manager.add_message(self.display_name, self.persona_name, response.text, response.emotion, log_file=response.log_path)


  def on_e_advance(self, event, state, scene_event=None):
      logging.debug(f"Advancing Behavior {self.name} from state {state.id}")


  def after_e_advance(self, event, state, scene_event=None):
    logging.debug(f"After advancing Behavior {self.name} from state {state.id}")
    if self.data.flag_stop and state != self.s_stop:
      self.e_stop(scene_event=scene_event)

    if state == self.s_stop:
      self.e_final(scene_event=scene_event)


  def after_e_stop(self, event, state, scene_event=None):
      if state == self.s_stop:
        self.e_final(scene_event=scene_event)  


  def _process_events(self):
    """Call the appropriate callback for speech or LLM prompt."""
    logging.debug(f"Processing events, {len(self.data._events)} - {self.current_state.id}")

    if( self.data.next_process_time and 
        datetime.now() < self.data.next_process_time):
      logging.debug(f"Waiting for next process time {self.data.next_process_time}")
      return
    else:
      self.data.next_process_time = None

    while len(self.data._events) > 0:
      event = self.data._events.pop(0)
      event_type =  event.tag
      # print(event_type)
      if event_type == "speak":
        self._speech_callback(event)

      elif event_type == "prompt":
        self.data._responses = [ resp for resp in self.data._responses if resp.speak_immediate]
        self._llm_callback(event)

      elif event_type == "meatstate":
        self._meatstate_callback(event)
        # if event.timeout > 0:
        #   logging.info(f"Setting next process time to {datetime.now() + timedelta(seconds=event.timeout)}")
        #   self.data.next_process_time = datetime.now() + timedelta(seconds=event.timeout)
        #   break
        # else:
        #   self.data.next_process_time = None

      elif event_type == "glitch":
        self.scene_manager.model.glitch = event.glitch
      
      elif event_type == "play":
        self._meatplay_callback(event)
      elif event_type == None:
        self.data.flag_stop = True
      else:
        logging.warning(f"Unknown event type {event_type}")

    # self.data._events = []


  def _process_responses(self):
    logging.debug(f"Processing responses, {len(self.data._responses)} - {self.current_state.id}")
    for response in self.data._responses:
      if response.speak_immediate or self.data.auto_speak or True:
        try:
          self.e_speak()
        except statemachine.exceptions.TransitionNotAllowed as e:
          logging.warning(f"{self.name}: {e}")
        break


  def override(self, name_override: str):
    override_events = self._overrides.get(name_override)
    if override_events:
      self.data._events = []
      self.data._events.extend(override_events)
      self.e_advance()
    else:
      logging.warning(f"Unknown override {name_override}")


  def _import_yaml(self, default_overrides):
    # logging.info(f"Importing YAML from {_yaml_path}")
    # Parse the YAML.
    self.data.scene_metadata = self._yaml["meta"]

    if "init" in self._yaml:
      self._init      = InitEvents(self._yaml["init"], **self.data.scene_metadata)
    else:
      self._init = None
      # raise Exception(f"State Machine {self.name}: missing 'init' state")

    if "end" in self._yaml:
      self._ends      = EndEvents(self._yaml["end"], **self.data.scene_metadata)
    else:
      self._ends = None


    if "dynamic" in self._yaml:
      self._dynamics  = DynamicEvents(self._yaml["dynamic"], **self.data.scene_metadata)
    else:
      self._dynamics = None

    self._overrides = OverrideEvents(default_overrides, **self.data.scene_metadata)
    if "override" in self._yaml:
      self._overrides += OverrideEvents(self._yaml["override"], **self.data.scene_metadata)
