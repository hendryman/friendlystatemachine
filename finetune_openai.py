# python3 finetune_openai.py --file_examples_json data/training_data.jsonl --create_new_job True
# python3 finetune_openai.py --job_finetuning ftjob-xNZwLlZeSWvpmRnHIMVannPR

import logging

import argparse
import datetime
import json
import os
import sys

import openai


parser = argparse.ArgumentParser(description="Fine-tuning interface for ChatGPT.")
parser.add_argument("--name_finetuning_job", type=str, help="Name of the finetuning job",
                    default=datetime.datetime.now().strftime("friendly-fire-%Y%m%d_%H%M%S"))
parser.add_argument("--file_examples_json", type=str,
                    help="File with examples in JSONL format",
                    default=None)
parser.add_argument("--job_finetuning", type=str,
                    help="Name of the finetuning job",
                    default=None)
parser.add_argument("--kill_current_jobs", type=bool,
                    help="Do we kill current finetuning jobs?",
                    default=False)
parser.add_argument("--create_new_job", type=bool,
                    help="Do we create a fine-tuning job?",
                    default=False)
opts, unknown = parser.parse_known_args()
print(opts)


def configure_openai():
  openai.api_key = os.getenv("OPENAI_API_KEY")
  assert openai.api_key, "Please set OPENAI_API_KEY environment variable"
  logging.getLogger("openai").setLevel(logging.WARNING)
  print(f"Configured OpenAI with OPENAI_API_KEY={openai.api_key}")
  openai_client = openai.OpenAI()
  return openai_client


client = configure_openai()

# Kill all existing fine-tuning jobs and exit.
if opts.kill_current_jobs:
  list_finetuning_jobs = client.fine_tuning.jobs.list(limit=10)
  print(f"[finetune] List of fine-tuning jobs:\n{list_finetuning_jobs}")
  for job in list_finetuning_jobs["data"]:
    print(f"[finetune] Kill finetuning jobs {job['id']}")
    client.fine_tuning.jobs.cancel(job["id"])
  exit(1)

# Create the fine-tuning file and fine-tuning job.
if opts.create_new_job:
  # Create the fine-tuning file first.
  finetuning_file_info = client.files.create(
    file=open(opts.file_examples_json, "rb"),
    purpose='fine-tune'
  )
  print(f"[finetune] Status:\n{finetuning_file_info}")
  finetuning_file = finetuning_file_info.id

  # Create the fine-tuning 
  print(f"[finetune] Creating fine-tuning for file {finetuning_file}...")
  finetuning_job_info = client.fine_tuning.jobs.create(training_file=finetuning_file, model="gpt-4o-mini-2024-07-18")
  print(finetuning_job_info)


if opts.job_finetuning:
  res = client.fine_tuning.jobs.retrieve(opts.job_finetuning)
  print(f"[finetuning] Finetuning job info:\n{res}")
  res = client.fine_tuning.jobs.list_events(fine_tuning_job_id=opts.job_finetuning, limit=10)
  print(f"[finetuning] Finetuning job list of events:\n{res}")
