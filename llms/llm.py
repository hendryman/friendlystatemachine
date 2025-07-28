import logging


from .defaults import available_llms, default_llm, DICT_LLMS
from .groq_chat import configure_groq, get_groq_llm_response
from .ollama_chat import configure_ollama, get_ollama_llm_response
from .openai_chat import configure_openai, get_llm_instruct_response, get_gpt_response
from .openrouter_chat import configure_openrouter, get_openrouter_response
from .xai_chat import configure_incel, get_incel_response


class LLM:

  def __init__(self, name_model):
    if name_model in available_llms("gpt3"):
      self._client = configure_openai()
      self._name_model = name_model
    elif name_model in available_llms("gpt4"):
      self._client = configure_openai()
      self._name_model = name_model
    elif name_model in available_llms("groq"):
      self._client = configure_groq()
      self._name_model = name_model
    elif name_model in available_llms("ollama"):
      configure_ollama()
      self._name_model = name_model
    elif name_model in available_llms("xai"):
      self._client = configure_incel()
      self._name_model = name_model
    elif name_model in available_llms("openrouter"):
      self._client = configure_openrouter()
      self._name_model = name_model
    else:
      raise Exception(f"Unknown LLM: {name_model}")
    logging.info(f"[LLM] Initialising {name_model}")


  @staticmethod
  def default_name():
    return default_llm("gpt4")


  @staticmethod
  def list_llms():
    res = []
    for family_name in DICT_LLMS:
      res.extend(available_llms(family_name))
    return res


  def call(self, prompt, timestamp, callback, personae = None, take_first_line: bool = True):
    if self._name_model in available_llms("gpt3"):
      return get_llm_instruct_response(self._client, callback, personae, model_name=self._name_model, prompt=prompt, timestamp=timestamp, take_first_line=take_first_line)
    elif self._name_model in available_llms("gpt4"):
      return get_gpt_response(self._client, callback, personae, model_name=self._name_model, prompt=prompt, timestamp=timestamp, take_first_line=take_first_line)
    elif self._name_model in available_llms("groq"):
      return get_groq_llm_response(self._client, callback, personae, model_name=self._name_model, prompt=prompt, timestamp=timestamp, take_first_line=take_first_line)
    elif self._name_model in available_llms("ollama"):
      return get_ollama_llm_response(callback, personae, model_name=self._name_model, prompt=prompt, timestamp=timestamp, take_first_line=take_first_line)
    elif self._name_model in available_llms("xai"):
      return get_incel_response(self._client, callback, personae, model_name=self._name_model, prompt=prompt, timestamp=timestamp, take_first_line=take_first_line)
    elif self._name_model in available_llms("openrouter"):
      return get_openrouter_response(self._client, callback, personae, model_name=self._name_model, prompt=prompt, timestamp=timestamp, take_first_line=take_first_line)
    else:
      raise Exception(f"Unknown LLM: {self._name_model}")


def test_llms():

  def _callback(prompt, response, timestamp):
    logging.info("*** Prompt:")
    logging.info(prompt)
    logging.info("*** Response:")
    logging.info(response)
    return response

  for family_name, llm_names in DICT_LLMS:
    for llm_name in llm_names:
      llm = LLM(llm_name)
      result = llm.call("What is your name?", 0, _callback)
      logging.info(f"{llm._name_model}: {result}")


if __name__ == "__main__":
  test_llms()
