import argparse
import json
import logging
import os
import pdfkit
import requests
import shutil
import time
import yaml
from dateutil.parser import parse
from collections import OrderedDict

from state_machine.messagehub import MessageHubClient


def load_typeform_config(config_yaml_path):
  try:
    with open(config_yaml_path) as f:
      try:
        config = yaml.safe_load(f)
      except yaml.parser.ParserError as e:
        logging.error(f"Error parsing config '{config_yaml_path}': {e}")
        exit(1)

  except Exception as e:
    logging.error(f"Error loading scene '{config_yaml_path}': {e}")
    raise e
  return config


class BearerAuth(requests.auth.AuthBase):
  def __init__(self, token):
    self.token = token

  def __call__(self, r):
    r.headers["authorization"] = "Bearer " + self.token
    return r


def generate_pdf(responses, args):

  timestamp = responses["timestamp"].replace("T", "_").replace("Z", "").replace("/", "")
  date_only = responses["timestamp"].split("T")[0].replace("-", "/")
  first_name = responses["first_name"][0]
  last_name = responses["last_name"][0]

  # Make a copy of the template and replace placeholders with responses.
  shutil.copy(args.template_file, args.temporary_file)
  with open(args.temporary_file, encoding="utf8") as f:
    doc = f.read()
  for key, response in responses.items():
    if key != "timestamp":
      text, placeholder = response
      doc = doc.replace(placeholder, text)  
  doc = doc.replace("_FF_LOCATION_", args.location)
  doc = doc.replace("_FF_DATE_", date_only)

  with open(args.temporary_file, 'w') as f:
    f.write(doc)

  # Create the pdf filename.
  filename_pdf = f"{timestamp}_{first_name}_{last_name}.pdf"
  filename_pdf = filename_pdf.replace(" ", "_")
  filename_pdf = os.path.join(args.path_consent_forms, filename_pdf)

  # You need to download an HTML to PDF converter: https://wkhtmltopdf.org/downloads.html
  pdfkit.from_file(args.temporary_file, filename_pdf)


def process_new_record(timestamp, record, config):
  """Process a new record with the expected config."""
  if "answers" not in record:
    return None

  responses = {"timestamp": timestamp}
  idx = 0
  for field in record["answers"]:
    try:
      # Match the record with expected config.
      field_id = field["field"]["id"]
      for field_config in config["fields"]:
        if field_config["field_id"] == field_id:
          break
      if field_config["field_id"] != field_id:
        logging.warning("Could not find field ID %s", field_id)
        logging.warning(record)
        return None

      # Store the response.
      field_type = field["type"]
      field_name = field_config["field_name"]
      placeholder = field_config["placeholder"]
      if field_config["type"] != field_type:
        logging.warning("Expected field type %s for %s, got %s",
                        field_config["type"], field_name, field_type)
        logging.warning(record)
        return None
      if field_type == "choice":
        responses[field_name] = (str(field[field_type]["label"]), placeholder)
      elif field_type == "choices":
        if "labels" in field[field_type]:
          responses[field_name] = [response for response in field[field_type]["labels"]]
        if "other" in field[field_type]:
          responses[field_name] = [response for response in field[field_type]["other"]]
        responses[field_name] = (", ".join(responses[field_name]), placeholder)
      else:
        responses[field_name] = (str(field[field_type]), placeholder)
    except Exception as e:
      logging.warning(f"Error processing field {field_id}: {e}")
  return responses


def parse_args():
  """Parse the args for the typeform server."""
  parser = argparse.ArgumentParser(description='Run the typeform bot')
  parser.add_argument('--log', type=str, default='INFO', help='Log level')
  parser.add_argument('--message_hub', type=str, default='http://127.0.0.1:8005', help='Message hub hostname and port')
  parser.add_argument('--config_yaml_path', type=str, default='typeform_client/typeform_config.yaml', help='Yaml file with config.')
  parser.add_argument('--template_file', type=str, default='typeform_client/templates/FriendlyFire_UserForm.html', help='HTML template for the form.')
  parser.add_argument('--temporary_file', type=str, default='typeform_client/templates/temp.html', help='HTML template for the form.')
  parser.add_argument('--path_consent_forms', type=str, default='consent_forms/', help='Path where consent forms live.')
  parser.add_argument('--location', type=str, default='Berne', help='Location of the installation.')
  parser.add_argument('--typeform_file', type=str, default='output/typeform.json', help='Location of the temporary typeform file.')
  return parser.parse_args()


def main():

  # Get the Typeform field names and form ID.
  args = parse_args()
  config = load_typeform_config(args.config_yaml_path)
  FORMAT = '%(asctime)s %(levelname)s: %(message)s [%(filename)s:%(lineno)s]'
  logging.basicConfig(format=FORMAT, level=args.log)
  logging.info(f"run_typeform.py: config: {config}")

  # Message Hub client.
  client = MessageHubClient(server_url=args.message_hub)

  # Typeform URL to connect to.
  assert "typeform" in config
  assert "url" in config["typeform"]
  assert "form_id" in config["typeform"]
  url = config["typeform"]["url"].replace("_ID", config["typeform"]["form_id"])
  bearer_token = config["typeform"]["token"]
  assert "fields" in config
  last_timestamp = None

  processed_records = OrderedDict([])
  while True:
    results = requests.get(url, auth=BearerAuth(bearer_token))
    results = json.loads(results.text)
    records = results["items"]
    for record in records:
      timestamp = record["landed_at"]
      if timestamp not in processed_records:
        logging.info(f"Found new record with timestamp {timestamp}")
        try:
          responses = process_new_record(timestamp, record, config)
          processed_records[timestamp] = responses
          logging.info(f"Processed record {timestamp}")

        except Exception as e:
          logging.error(f"Error processing record {timestamp}: {e}")
          logging.error(record)
          continue

    processed_records = OrderedDict(sorted(processed_records.items(), key=lambda t: parse(t[0])))
    newest_record = processed_records.popitem()[1] if len(processed_records) > 0 else None

    newest_timestamp = parse(newest_record["timestamp"]) if newest_record is not None else None

    if newest_record is not None and (last_timestamp is None or  newest_timestamp > last_timestamp):
      # logging.info(responses)
      # generate_pdf(responses, args)
      #client.send_message("typeform", json.dumps({"data": responses}))

      with open(args.typeform_file, "w") as f:
        logging.info(f"Writing to {args.typeform_file}")
        f.write(json.dumps(newest_record))

      last_timestamp = parse(newest_record["timestamp"])


    time.sleep(1)


if __name__ == "__main__":
  main()
