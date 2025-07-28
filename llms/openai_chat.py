import logging

import os

import openai

from .defaults import default_llm, extract_response, split_prompt_into_system_user


def configure_openai():
  openai.api_key = os.getenv("OPENAI_API_KEY")
  assert openai.api_key, "Please set OPENAI_API_KEY environment variable"
  logging.getLogger("openai").setLevel(logging.WARNING)
  print(f"Configured OpenAI with OPENAI_API_KEY={openai.api_key}")
  openai_client = openai.OpenAI()
  return openai_client


def get_llm_instruct_response(openai_client,
                              callback,
                              personae = None,
                              model_name: str = default_llm("gpt3"),
                              prompt: str = "",
                              timestamp: int = 0,
                              take_first_line: bool = True):

  if personae:
    comp_args = {
        "stop"             : personae['gpt_stop'],
        "temperature"      : personae['gpt_temperature'],
        "top_p"            : personae['gpt_top'],
        "frequency_penalty": personae['gpt_pen_freq'],
        "presence_penalty" : personae['gpt_pen_pres'],
        "max_tokens"       : personae['gpt_max_tokens']
    }
  else:
    comp_args = {
        "stop"             : "",
        "temperature"      : 0.9,
        "top_p"            : 1,
        "frequency_penalty": 1,
        "presence_penalty" : 1,
        "max_tokens"       : 60
    }     

  try:
    response_obj = openai_client.completions.create(
        model=default_llm("gpt3"),
        prompt=prompt,
        n=1,
        **comp_args
    )
    response = response_obj.choices[0].text
    response = extract_response(response, take_first_line)
    return callback(prompt, response.strip(), timestamp)

  except Exception as e:
    logging.warning(e)
  return callback(prompt, None, timestamp)


def get_gpt_response(openai_client,
                     callback,
                     personae = None,
                     model_name: str = default_llm("gpt4"),
                     prompt: str = "",
                     timestamp: int = 0,
                     take_first_line: bool = False):

  if personae:
    comp_args = {
        "stop"             : personae['gpt_stop'],
        "temperature"      : personae['gpt_temperature'],
        "top_p"            : personae['gpt_top'],
        "frequency_penalty": personae['gpt_pen_freq'],
        "presence_penalty" : personae['gpt_pen_pres'],
        "max_tokens"       : personae['gpt_max_tokens']
    }
  else:
    comp_args = {
        "stop"             : "",
        "temperature"      : 0.9,
        "top_p"            : 1,
        "frequency_penalty": 1,
        "presence_penalty" : 1,
        "max_tokens"       : 60
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
    response_obj = openai_client.chat.completions.create(
      messages=messages, model=default_llm("gpt4"))
    # print(response_obj)
    response = response_obj.choices[0].message.content
    if take_first_line:
      response = response.split("\n")[0]
    return callback(prompt, response.strip(), timestamp)

  except Exception as e:
    logging.warning(e)
  return callback(prompt, None, timestamp)



def test_gpt_3_5_turbo_instruct():
  def _callback(prompt, response, timestamp):
    logging.info("*** Prompt:")
    logging.info(prompt)
    logging.info("*** Response:")
    logging.info(response)
    return response

  openai_client = configure_openai()
  result = get_llm_instruct_response(openai_client, "What is your name?", 0, _callback)
  print(result)



def test_gpt_4o_mini():
  def _callback(prompt, response, timestamp):
    logging.info("*** Prompt:")
    logging.info(prompt)
    logging.info("*** Response:")
    logging.info(response)
    return response

  openai_client = configure_openai()
  result = get_gpt_response(openai_client, "What is your name?", 0, _callback)
  print(result)


if __name__ == "__main__":
  test_gpt_3_5_turbo_instruct()
  test_gpt_4o_mini()
