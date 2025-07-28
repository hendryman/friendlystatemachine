from enum import Enum
import logging
from typing import Any

import random
import time
from collections import defaultdict


#####################
# Event Components #
#####################

class EventComponent(object):
  tag = None
  allowed = []


  def __init__(self, yaml_obj):
    if not yaml_obj:
      self.value = self.get_default()
      return
    
    value = yaml_obj.get(self.tag, None)
    if value:
      if isinstance(value, str):
        assert value in self.allowed, f"{self.tag} {value} not in {self.allowed}"
      elif isinstance(value, dict):
        pass 

      self.value = value
    else:
      self.value = self.get_default()


  def get(self):
    return self.value


  def get_default(self):
    logging.warning(f"Default value for {self.tag} not implemented")
    raise NotImplementedError



class MeatState(EventComponent):
  allowed = [
    "idle", "think", "speak", "listen"
  ]
  tag = "meatstate"

  def __init__(self, yaml_obj):
    super().__init__(yaml_obj)



class SpeakingStyle(EventComponent):

  allowed = [
      "Default",
      "Sad",
      "Cheerful",
      "Terrified",
      "Unfriendly",
      "Angry",
      "Excited",
      "Shouting",
      "Whispering",
      "Friendly",
      "Hopeful"
  ]
  tag = "azure_style"

  def __init__(self, yaml_obj):
    super().__init__(yaml_obj)


  def get_default(self):
    return "Default"


  def get(self):

    if self.value == "Angry":
      return {
        "style": self.value,
        "degree": 1.2,
        "pause": 100,
        "pitch": -6,
        "rate": 1,
        "volume": 10
      }
    elif self.value == "Sad":
      return {
      "style": self.value,
      "degree": 0.3,
      "pause": 350,
      "pitch": -5,
      "rate": 2,
      "volume": 0
      }
    elif self.value == "Cheerful":
      return {
      "style": self.value,
      "degree": 0.3,
      "pause": 350,
      "pitch": -5,
      "rate": 2,
      "volume": 0
      }
    elif self.value == "Excited":
      return {
      "style": self.value,
      "degree": 0.5,
      "pause": 200,
      "pitch": -5,
      "rate": +2,
      "volume": 0
      }
    elif self.value == "Shouting":
      return {
      "style": self.value,
      "degree": 1.2,
      "pause": 100,
      "pitch": -5,
      "rate": +8,
      "volume": 0
      }
    elif self.value == "Terrified":
      return {
      "style": self.value,
      "degree": 1.1,
      "pause": 100,
      "pitch": -5,
      "rate": -2,
      "volume": 0
      }
    elif self.value == "Unfriendly":
      return {
      "style": self.value,
      "degree": 0.8,
      "pause": 250,
      "pitch": -3,
      "rate": +3,
      "volume": 0
      }
    elif self.value == "Whispering":
      return {
      "style": self.value,
      "degree": 1.2,
      "pause": 350,
      "pitch": -5,
      "rate": 2,
      "volume": 0
      }
    elif self.value == "Friendly":
      return {
      "style": self.value,
      "degree": 0.3,
      "pause": 350,
      "pitch":-5,
      "rate": +2,
      "volume": 0
      }
    elif self.value == "Hopeful":
      return {
      "style": self.value,
      "degree": 0.7,
      "pause": 280,
      "pitch": -5,
      "rate": +3,
      "volume": 0
      }
    else:
      return {
        "style": self.value,
        "degree": 1,
        "pause": 350,
        "pitch": -5,
        "rate": +2,
        "volume": 0
      }


class Emotion(EventComponent):

  allowed = [
      "neutral",
      "anger",
      "fear",
      "sadness",
      "joy",
      "disgust"
  ]
  tag = "emotion"

  def __init__(self, yaml_obj):
    super().__init__(yaml_obj)


  def get_default(self):
    return "neutral"


  def get(self):
    return {
        "sadness": 0.5 if self.value == "sadness" else 0,
        "joy"    : 0.5 if self.value == "joy"     else 0,
        "fear"   : 0.5 if self.value == "fear"    else 0,
        "disgust": 0.5 if self.value == "disgust" else 0,
        "anger"  : 0.5 if self.value == "anger"   else 0
    }
    


class Animation(EventComponent):

  allowed = [
      "eyeroll",
      "shirtcheck",
      "steam",
      "discoverfake",
      "lookleftright",
      "look_up",
      "affectionate",
      "bored",
      "circle_look",
      "growl",
      "judge",
      "left_look",
      "pounder",
      "scanning",
      "sceptic",
      "shrug",
      "smile",
      "weary"
  ]

  def __init__(self, yaml_obj):
    super().__init__(yaml_obj)


  def get_default(self):
    return ""


  def get(self):
    return {
      "animation": self.value,
      "speed":""
    }



class PreAnimation(Animation):
  tag = "preanimation"
  def __init__(self, animation):
    return super().__init__(animation)



class PostAnimation(Animation):
  tag = "postanimation"
  def __init__(self, animation):
    return super().__init__(animation)



class SG_Mood(EventComponent):

  allowed = [
      "neutral",
      "positive",
      "negative",
      "effort",
      "annoyed",
      "acknowledge"
  ]

  tag = "sg_mood"

  def get_default(self):
    return "neutral"


  def get(self):
    if isinstance(self.value, str):
      return {
        "mood": self.value,
        "scale": 0.5,
        "frequency": 1.0
      }
    elif isinstance(self.value, dict):
      return {
        "mood": self.value.get("mood", "neutral"),
        "scale": self.value.get("scale", 0.5),
        "frequency": self.value.get("frequency", 1.0)
      }


class Role(EventComponent):
  allowed = ["mask", "clerk"]
  tag = "role"
  def get_default(self):
    return "mask"



#####################
# Prompt and Speak #
#####################

class Prompt(object):
  """Class containing elements of a prompt (nested lists)."""

  def __init__(self, elements):
    if not isinstance(elements, list):
      raise Exception(f"Prompt needs to be a list: {elements}")
    for element in elements:
      if not isinstance(element, str) and not isinstance(element, list):
        raise Exception(f"Prompt element needs to be a string or a list of strings: {element}")
      if isinstance(element, list) and not all(isinstance(n, str) or n is None for n in element):
        raise Exception(f"Prompt element needs to be a list of strings: {element}")
    self.elements = elements


  def get(self):
    """Assemble the prompt, sampling from any nested list."""
    prompt = ''
    for item in self.elements:
      if isinstance(item, str):
        prompt += item + '\n\n'
      if isinstance(item, list):
        instruction = random.choice(item)
        if instruction:
          prompt += instruction + '\n\n'
    return prompt.strip()



class Sentence(object):
  """Class storing a sentence or list of sentences to say."""

  def __init__(self, sentences: str | list[str]):
    if not isinstance(sentences, str) and not isinstance(sentences, list):
      raise Exception(f"Speak sentence(s) needs to be a string or a list of strings: {sentences}")
    if isinstance(sentences, list) and not all(isinstance(n, str) for n in sentences):
      raise Exception(f"Speak sentences needs to be a list of strings: {sentences}")
    self.sentences = sentences


  def get(self) -> str:
    if isinstance(self.sentences, list):
      return random.choice(self.sentences)
    else:
      return self.sentences



#####################
# Event Classes     #
#####################
class Event(object):
  
  def __init__(self, tag: str):
    self.tag = tag

  def get_event_tag(dictionary):
    try:
      valid_keys = Event.get_event_types_lookup().keys()
      keys = set(dictionary.keys())
      tags = keys.intersection(valid_keys)
      if len(tags) == 1:
        return tags.pop()
      else:
        # logging.warning(f"Invalid event must have exacly one of {valid_keys} but has {keys} ")
        return None
    except Exception as e:
      # logging.warning(f"Invalid event {dictionary}: {e}")
      return None
  

  def get_event_types_lookup():
      def recursive_subclasses(cls):
          subclasses = set()
          for subclass in cls.__subclasses__():
              subclasses.add(subclass)
              subclasses.update(recursive_subclasses(subclass))
          return subclasses

      event_types = recursive_subclasses(Event) 
     
      return {cls.tag: cls for cls in event_types if hasattr(cls, 'tag')}



class GlitchEvent(Event):
  tag = "glitch"
  def __init__(self, yaml_obj):
    super().__init__(GlitchEvent.tag)
    self.glitch = {
      "active"  : yaml_obj["glitch"]["active"],
      "duration": yaml_obj["glitch"]["duration"] if "duration" in yaml_obj["glitch"] else 0,
      "start"   : yaml_obj["glitch"]["start"]    if "start"    in yaml_obj["glitch"] else 0.5,
      "end"     : yaml_obj["glitch"]["end"]      if "end"      in yaml_obj["glitch"] else 0.5
    } 

class StateEvent(Event):
  tag = "meatstate"
  def __init__(self, yaml_obj):
    super().__init__(StateEvent.tag)
    self.meatstate = yaml_obj["meatstate"]
    self.timeout   = yaml_obj["timeout"] if "timeout" in yaml_obj else 0


class PlayEvent(Event):
  tag = "play"
  def __init__(self, yaml_obj):
    super().__init__(PlayEvent.tag)
    self.id             = int(yaml_obj["play"])
    self.emotion        = Emotion(yaml_obj)
    self.pre_animation  = PreAnimation(yaml_obj)
    self.post_animation = PostAnimation(yaml_obj)
    self.sg_mood        = SG_Mood(yaml_obj)

  def get_meat_event_args(self):
    return {
      "channel": "play",
      "emotion": self.emotion,
      "pre_animation": self.pre_animation,
      "post_animation": self.post_animation,
      "sg_mood": self.sg_mood
    }


class MeatEvent(Event):
  def __init__(self, tag, yaml_obj):
    super().__init__(tag)
    self.emotion        = Emotion(yaml_obj)
    self.azure_style    = SpeakingStyle(yaml_obj)
    self.pre_animation  = PreAnimation(yaml_obj)
    self.post_animation = PostAnimation(yaml_obj)
    self.sg_mood        = SG_Mood(yaml_obj)
    self.role           = Role(yaml_obj)

  def get_meat_event_args(self):
    return {
      "channel": "say",
      "emotion": self.emotion,
      "azure_style": self.azure_style,
      "pre_animation": self.pre_animation,
      "post_animation": self.post_animation,
      "sg_mood": self.sg_mood,
      "role": self.role
    }


class PromptEvent(MeatEvent):
  tag = "prompt"
  def __init__(self, yaml_obj):
    super().__init__(PromptEvent.tag, yaml_obj)
    self.prompt = Prompt(yaml_obj["prompt"])



class SpeakEvent(MeatEvent):
  tag = "speak"
  def __init__(self, yaml_obj):
    super().__init__(SpeakEvent.tag, yaml_obj)
    self.speak = Sentence(yaml_obj["speak"])


class EventClass(object):

  def __init__(self,
               default_event:  str,
               yaml_obj,
               *args, **kwargs
    ):
    self.default_event = default_event 
    self.event_sequences = defaultdict(list)

    if isinstance(yaml_obj, list):
      for _yaml_obj in yaml_obj:
        if not isinstance(_yaml_obj, dict):
          raise Exception(f"Event must be a dictionary: {_yaml_obj}")
        tag = Event.get_event_tag(_yaml_obj)
        if(tag):
          eventType = Event.get_event_types_lookup()[tag]
          self.event_sequences[self.default_event].append(eventType(_yaml_obj))
        else:
          raise Exception(f"Not a valid event tag.\n{_yaml_obj}")  
    elif isinstance(yaml_obj, dict):
      tag = Event.get_event_tag(yaml_obj)
      if(tag):
          eventType = Event.get_event_types_lookup()[tag]
          self.event_sequences[self.default_event].append(eventType(yaml_obj))
      else:
        for key, _yaml_obj in yaml_obj.items():
          if isinstance(_yaml_obj, list):
            for __yaml_obj in _yaml_obj:
              tag = Event.get_event_tag(__yaml_obj)
              if(tag):
                eventType = Event.get_event_types_lookup()[tag]
                self.event_sequences[key].append(eventType(__yaml_obj))
              else:
                raise Exception(f"Not a valid event tag.\n{_yaml_obj}")
          elif isinstance(_yaml_obj, dict):
            tag = Event.get_event_tag(_yaml_obj)
            if(tag):
              eventType = Event.get_event_types_lookup()[tag]
              self.event_sequences[key].append(eventType(_yaml_obj))
            else:
              raise Exception(f"Not a valid event tag.\n{_yaml_obj}")       
          else:
            raise Exception(f"Event must be a dictionary or a list of dictionaries: {_yaml_obj}")
    else:
      raise Exception(f"EventClass needs to be a dict or a list of dicts: {_yaml_obj}")


  def get(self, key: str = None) -> Event:
    key = key or self.default_event
    if key in self.event_sequences:
      return self.event_sequences[key]
    else:
      logging.warning(f"Unknown event '{key}'")
      return None


  def __add__(self, other):
    for key, events in other.event_sequences.items():
      self.event_sequences[key].extend(events)
    return self


  def __iadd__(self, other):
    return self.__add__(other)



class DynamicEventsClass(EventClass):

  def __init__(self, 
               default_event:  str,
               yaml_obj, 
               loop:           bool,
               randomize:      bool,
               max_iterations: IndentationError,
               
               *args, **kwargs):
    
    self.looping        = loop
    self.randomize      = randomize
    self.max_iterations = max_iterations

    super().__init__(default_event, yaml_obj, *args, **kwargs)


  def get(self, key: str = None, counter: int = None) -> Event:
    event = super().get(key)
    if not event:
      return None

    # logging.debug(f"Getting event '{key}'[{counter}] from '{self.name}'")
    if self.max_iterations and counter and counter >= self.max_iterations:
      logging.debug(f"Event (max_iterations: {self.max_iterations}) has reached max iterations")
      return None

    if self.looping and counter >= len(event):
      counter = counter % len(event)

    # logging.info(f"Getting event '{key}'[{counter}/{len(event)}] from '{self.name}'")
    if counter == 0 and self.randomize:
      random.shuffle(event)

    if counter >= len(event):
      # logging.warning(f"Event has no events")
      return None
    
    return event[counter]

