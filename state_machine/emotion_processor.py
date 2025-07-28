import logging
import time

from transformers import AutoTokenizer, pipeline
from optimum.onnxruntime import ORTModelForSequenceClassification

from state_machine.entity import Emotion, SG_Mood, SpeakingStyle


from onnxruntime.capi.onnxruntime_pybind11_state import InvalidArgument


EMOTION_MODEL_ID = "SamLowe/roberta-base-go_emotions-onnx"
EMOTION_FILE_NAME = "onnx/model_quantized.onnx"
MAX_LEN_TEXT_EMOTION = 1500


class EmotionProcessor:

  def __init__(self,
               emotion_decay: float = 0.67,
               coeff_sentiment: float = 0.5,
               non_neutral_thres_low: float = 0.25,
               non_neutral_thres_medium: float = 0.5,
               non_neutral_thres_high: float = 0.75):
    self.reset()
    self._emotion_decay = emotion_decay
    self._coeff_sentiment = coeff_sentiment
    self._non_neutral_thres_low = non_neutral_thres_low
    self._non_neutral_thres_medium = non_neutral_thres_medium
    self._non_neutral_thres_high = non_neutral_thres_high

    self._model = ORTModelForSequenceClassification.from_pretrained(
        EMOTION_MODEL_ID, file_name=EMOTION_FILE_NAME)


    self._tokenizer = AutoTokenizer.from_pretrained(EMOTION_MODEL_ID)
    self._onnx_classifier = pipeline(
        task="text-classification",
        model=self._model,
        tokenizer=self._tokenizer,
        top_k=None,
        function_to_apply="sigmoid",
    )


  def reset(self):
    self._emotion = {
        "anger": 0,
        "disgust": 0,
        "fear": 0,
        "joy": 0,
        "sadness": 0,
    }
    self._speaking_style = "Default"
    self._sg_mood = "neutral"


  def print_emotion_state(self):
    s = ""
    for k in sorted(self._emotion.keys()):
      val = self._emotion[k]
      s += f"{k}{val:.2f} "
    return s


  def _change_speaking_style(self):
    if (self._speaking_style == "Default" and
        (self._emotion["anger"] > self._non_neutral_thres_high or
         self._emotion["disgust"] > self._non_neutral_thres_high)):
      logging.info(f"Overriding Default because speaker in high angry/disgusted state.")
      self._speaking_style = "Shouting"
    elif (self._speaking_style == "Default" and
          (self._emotion["anger"] > self._non_neutral_thres_medium or
           self._emotion["disgust"] > self._non_neutral_thres_medium)):
      logging.info(f"Overriding Default because speaker in medium angry/disgusted state.")
      self._speaking_style = "Angry"
    elif (self._speaking_style == "Default" and
          (self._emotion["anger"] > self._non_neutral_thres_low or
           self._emotion["disgust"] > self._non_neutral_thres_low)):
      logging.info(f"Overriding Default because speaker in low angry/disgusted state.")
      self._speaking_style = "Unfriendly"
    elif (self._speaking_style == "Default" and
          self._emotion["fear"] > self._non_neutral_thres_high):
      logging.info(f"Overriding Default because speaker in high fearful state.")
      self._speaking_style = "Terrified"
    elif (self._speaking_style == "Default" and
          self._emotion["fear"] > self._non_neutral_thres_medium):
      logging.info(f"Overriding Default because speaker in fearful state.")
      self._speaking_style = "Whispering"
    elif (self._speaking_style == "Default" and
          self._emotion["sadness"] > self._non_neutral_thres_low):
      logging.info(f"Overriding Default because speaker in sad state.")
      self._speaking_style = "Sad"
    elif (self._speaking_style == "Default" and
          self._emotion["joy"] > self._non_neutral_thres_high):
      logging.info(f"Overriding Default because speaker in high joy state.")
      self._speaking_style = "Cheerful"
    elif (self._speaking_style == "Default" and
          self._emotion["joy"] > self._non_neutral_thres_medium):
      logging.info(f"Overriding Default because speaker in joy state.")
      self._speaking_style = "Excited"
    elif (self._speaking_style == "Default" and
          self._emotion["joy"] > self._non_neutral_thres_low):
      logging.info(f"Overriding Default because speaker in low joy state.")
      self._speaking_style = "Friendly"


  def from_meat_event(self, meat_event_args):
    meat_event = meat_event_args.copy()
    logging.info(f"from_meat_event")

    # Emotions are provided as a dict with keys: "anger", "disgust", "fear", "joy", "sadness".
    # We use a simple exponential decay filter.
    # logging.info(f"Meat event: {meat_event['emotion'].get()}")
    emotion = "neutral"
    emotion_max = 0.0
    for k in self._emotion:
      self._emotion[k] = min(self._emotion[k] * self._emotion_decay + meat_event["emotion"].get()[k], 1.0)
      if self._emotion[k] > emotion_max and self._emotion[k] > self._non_neutral_thres_low:
        emotion = k
        emotion_max = self._emotion[k]
    meat_event["emotion"].value = emotion
    # logging.info(f"Integrated meat event: {meat_event['emotion'].value}")

    # Speaking styles can be: "Angry", "Cheerful", "Default", "Excited", "Hopeful" "Friendly",
    # "Sad", "Shouting", "Terrified", "Unfriendly", "Whispering".
    # We override with any speaking style other than "Default", otherwise we check the emotion state.
    # logging.info(f"Meat event: {meat_event['azure_style'].get()}")
    if "azure_style" in meat_event:
      azure_style = meat_event["azure_style"].value
      if azure_style != "Default":
        self._speaking_style = azure_style
      elif (self._speaking_style in ["Angry", "Shouting", "Unfriendly"] and
            (self._emotion["anger"] > self._non_neutral_thres_low or
            self._emotion["disgust"] > self._non_neutral_thres_low)):
        logging.info(f"Overriding Default because speaker in angry/disgusted state.")
      elif (self._speaking_style in ["Cheerful", "Excited", "Friendly", "Hopeful"] and
            self._emotion["joy"] > self._non_neutral_thres_low):
        logging.info(f"Overriding Default because speaker in joyful state.")
      elif (self._speaking_style in ["Sad", "Terrified", "Whispering"] and
            (self._emotion["fear"] > self._non_neutral_thres_low or
            self._emotion["sadness"] > self._non_neutral_thres_low)):
        logging.info(f"Overriding Default because speaker in sad/fearful state.")
      self._change_speaking_style()
      meat_event["azure_style"].value = self._speaking_style
    # logging.info(f"Integrated meat event: {meat_event['azure_style'].value}")

    # SG mood can be: "neutral", "positive", "negative", "effort", "annoyed", "acknowledge"
    # logging.info(f"Meat event: {meat_event['sg_mood'].get()}")
    return meat_event


  def classify_text(self, text: str):
    t0 = time.time()
    try:
      text = text[(-min(len(text), MAX_LEN_TEXT_EMOTION)):]
      res = self._onnx_classifier([text])[0]
      t1 = time.time()
      logging.info(f"Text classified as {res[0]['label']} with score {res[0]['score']:.2} in {t1-t0:.3}s")
      for elem in res:
        if elem["label"] in ["admiration", "amusement", "caring", "desire", "excitement", "gratitude", "joy", "love", "optimism", "pride", "relief"]:
          self._emotion["joy"] += elem["score"] * self._coeff_sentiment
        if elem["label"] in ["anger", "annoyance"]:
          self._emotion["anger"] += elem["score"] * self._coeff_sentiment
        if elem["label"] in ["confusion", "disappointment", "disapproval", "disgust", "embarrassment"]:
          self._emotion["disgust"] += elem["score"] * self._coeff_sentiment
        if elem["label"] in ["fear", "nervousness"]:
          self._emotion["fear"] += elem["score"] * self._coeff_sentiment
        if elem["label"] in ["grief", "remorse", "sadness"]:
          self._emotion["sadness"] += elem["score"] * self._coeff_sentiment
      for k in self._emotion:
        self._emotion[k] = min(self._emotion[k], 1.0)
    except InvalidArgument as e:
      logging.warning(f"Error classifying text: {e}")
      logging.warning("Classifying only second half instead.")
      self.classify_text(text[(len(text)//2):])


  def from_user(self, user_emotion):
    # The user model predicts the following emotions:
    # "Angry", "Sad", "Happy", "Surprise", "Fear", "Disgust", "Contempt", "Neutral"
    logging.info(f"User emotion: {user_emotion}")
    if user_emotion == "Angry":
      self._emotion["anger"] += 2
    elif user_emotion == "Sad":
      self._emotion["sadness"] += 2
    elif user_emotion == "Happy" or user_emotion == "Surprise":
      self._emotion["joy"] += 2
    elif user_emotion == "Fear":
      self._emotion["fear"] += 2
    elif user_emotion == "Disgust" or user_emotion == "Contempt":
      self._emotion["disgust"] += 2
    for k in self._emotion:
      self._emotion[k] = min(self._emotion[k], 1.0)
    self._change_speaking_style()
    pass


  def overwrite_with_emotion_state(self, response_meat_event):
    meat_event = response_meat_event.copy()
    emotion = "neutral"
    emotion_max = 0.0
    for k in self._emotion:
      if self._emotion[k] > emotion_max and self._emotion[k] > self._non_neutral_thres_low:
        emotion = k
        emotion_max = self._emotion[k]
    meat_event["emotion"].value = emotion
    if "azure_style" in meat_event:
      meat_event["azure_style"].value = self._speaking_style
      logging.info(f"Speaking meat event: {meat_event['azure_style'].get()}")
    logging.info(f"Speaking meat event: {meat_event['emotion'].get()}")
    return meat_event
