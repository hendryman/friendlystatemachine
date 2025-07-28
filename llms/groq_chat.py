import logging

import os

import groq

from .defaults import default_llm, extract_response, split_prompt_into_system_user


def configure_groq():
  groq_api_key = os.environ.get("GROQ_API_KEY")
  assert groq_api_key, "Please set GROQ_API_KEY environment variable"
  groq_client = groq.Groq(
      api_key=groq_api_key,
  )
  logging.getLogger("groq").setLevel(logging.INFO)
  print(f"Configured Groq with GROQ_API_KEY={groq_api_key}")
  return groq_client


def get_groq_llm_response(groq_client,
                          callback,
                          personae = None,
                          model_name: str = default_llm("groq"),
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
    response_obj = groq_client.chat.completions.create(
      messages=messages, model=default_llm("groq"))
    # print(response_obj)
    response = response_obj.choices[0].message.content
    response = extract_response(response, take_first_line)
    return callback(prompt, response.strip(), timestamp)

  except Exception as e:
    logging.warning(e)
  return callback(prompt, None, timestamp)


def test_llama_3_1_70b_groq():

  def _callback(prompt, response, timestamp):
    logging.info("*** Prompt:")
    logging.info(prompt)
    logging.info("*** Response:")
    logging.info(response)
    return response

  groq_client = configure_groq()
  model_name = default_llm("groq")
  result = get_groq_llm_response(groq_client, model_name, "What is your name?", 0, _callback)
  print(result)


if __name__ == "__main__":
  test_llama_3_1_70b_groq()
