import logging

import os

import ollama

from .defaults import default_llm, extract_response, split_prompt_into_system_user


def configure_ollama():
  logging.getLogger("ollama").setLevel(logging.INFO)


def get_ollama_llm_response(callback,
                            personae = None,
                            model_name: str = default_llm("ollama"),
                            prompt: str = "",
                            timestamp: int = 0,
                            take_first_line: bool = True):

  if personae:
    options = {
        "stop"             : personae['gpt_stop'],
        "temperature"      : personae['gpt_temperature'],
        "top_p"            : personae['gpt_top'],
        "frequency_penalty": personae['gpt_pen_freq'],
        "presence_penalty" : personae['gpt_pen_pres'],
        "num_predict"      : personae['gpt_max_tokens']
    }
  else:
    options = {
        "stop"             : ["\n"],
        "temperature"      : 0.9,
        "top_p"            : 1,
        "frequency_penalty": 1,
        "presence_penalty" : 1,
        "num_predict"      : 60
    }     

  system_prompt, user_prompt = split_prompt_into_system_user(prompt)
  messages = [
      {
          "role": "system",
          "content": system_prompt,
      },
      {
          "role": "user",
          "content": user_prompt,
      }
  ]

  try:
    response = ollama.chat(
      messages=messages, model=default_llm("ollama"), options=options)
    response = response["message"]["content"]
    response = extract_response(response, take_first_line)
    return callback(prompt, response.strip(), timestamp)

  except Exception as e:
    logging.warning(e)
  return callback(prompt, None, timestamp)


def test_llama_3_1_8b_ollama():

  def _callback(prompt, response, timestamp):
    logging.info("*** Prompt:")
    logging.info(prompt)
    logging.info("*** Response:")
    logging.info(response)
    return response

  configure_ollama()
  model_name = default_llm("ollama")
  result = get_ollama_llm_response(model_name, "What is your name?", 0, _callback)
  print(result)


if __name__ == "__main__":
  test_llama_3_1_8b_ollama()
