import argparse
import logging

from llms.llm import LLM


DEFAULT_TEMP_FILE = 'output/temp_prompt.txt'


def parse_args():
  parser = argparse.ArgumentParser(description='Run the friendly bot')
  parser.add_argument('--logfile', type=str, default='simulation', help='Filename of the log.')
  parser.add_argument('--tempfile', type=str, default='', help='Filename of the log.')
  parser.add_argument('--take_first_line', type=bool, default=False, help='Take the first line.')
  return parser.parse_args()


def _callback(prompt, response, timestamp):
  return response


def main():
  args = parse_args()

  if len(args.tempfile) > 0:
    print(f"Reading prompt from {args.tempfile}")    
    with open(args.tempfile) as f:
      prompt = f.read()
  else:
    print(f"Extracting prompt from {args.logfile}")    
    with open(args.logfile) as f:
    	lines = f.readlines()
    idx_from = lines.index("_____Prompt_____\n") + 1
    idx_to = lines.index("_____Response_____\n")
    prompt = "".join(lines[idx_from:idx_to])
    print(prompt)
    with open(DEFAULT_TEMP_FILE, 'w') as f:
      f.write(prompt)
    print(f"Saved prompt to {DEFAULT_TEMP_FILE}")

  for llm_name in LLM.list_llms():
  # for llm_name in ["grok-beta"]:
    llm = LLM(llm_name)
    result = llm.call(prompt, 0, _callback, take_first_line=args.take_first_line)
    print(f"{llm._name_model}:\n{result}\n")

if __name__ == "__main__":
  main()
