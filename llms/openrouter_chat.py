import logging

import os

import openai

from .defaults import default_llm, extract_response, split_prompt_into_system_user


def configure_openrouter():
  openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
  assert openrouter_api_key, "Please set OPENROUTER_API_KEY environment variable"
  logging.getLogger("openrouter").setLevel(logging.WARNING)
  print(f"Configured OpenRouter with OPENROUTER_API_KEY={openrouter_api_key}")
  openrouter_client = openai.OpenAI(
      api_key=openrouter_api_key,
      base_url="https://openrouter.ai/api/v1",
  )
  return openrouter_client


def get_openrouter_response(openrouter_client,
                            callback,
                            personae = None,
                            model_name: str = default_llm("openrouter"),
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
    response_obj = openrouter_client.chat.completions.create(
      messages=messages, model=default_llm("openrouter"))
    # print(response_obj)
    response = response_obj.choices[0].message.content
    response = extract_response(response, take_first_line)
    return callback(prompt, response.strip(), timestamp)

  except Exception as e:
    logging.warning(e)
  return callback(prompt, None, timestamp)


def test_openrouter():
  def _callback(prompt, response, timestamp):
    logging.info("*** Prompt:")
    logging.info(prompt)
    logging.info("*** Response:")
    logging.info(response)
    return response

  openrouter_client = configure_openrouter()
  result = get_openrouter_response(openrouter_client, "What is your name?", 0, _callback)
  print(result)


if __name__ == "__main__":
  test_openrouter()
