import argparse
import codecs
import chardet
from enum import Enum
import glob
import os
import re
import unidecode
import logging


# Regular expressions.
regexp_timestamp = re.compile('[0-9]+:[0-9]+:[0-9,]+ --> [0-9]+:[0-9]+:[0-9,]+')
regexp_parenthesis = re.compile('\([ ,\w]+\)')
regexp_brackets = re.compile('\[[ ,\w]+\]')
regexp_html = re.compile('<.*?>')


def parse_args():
  parser = argparse.ArgumentParser(description='Parse the subtitles.')
  parser.add_argument('--path', type=str, help='Path with .srt files')
  return parser.parse_args()


def validate_line_text(lines, text, line):
  """Process `line` and determine if we concatenate it to `text` and add to `lines`."""

  # Detect empty line, transition to next subtitle.
  if len(line) == 0:
    if len(lines) > 0 and not re.search('[.!\?]$', lines[-1]):
      # print(f'   [{lines[-1]}] + {text}')
      lines[-1] = lines[-1] + ' ' + text.strip()
    else:
      lines.append(text.strip())
    return '', True

  # Remove sound effects and HTML tags.
  line = regexp_parenthesis.sub('', line)
  line = regexp_brackets.sub('', line)
  line = regexp_html.sub('', line)
  line = line.strip()

  # Handle dialogue lines startwith -.
  if line.startswith('- '):
    if len(text) > 0:
      lines.append(text.strip())
      return line, False
    else:
      text += ' ' + line
      return text, False

  # Default behaviour.
  text += ' ' + line
  return text, False


class PhaseSRT(Enum):
  """.SRT files have 4 possible "states".""" 
  INDEX = 0
  TIMESTAMP = 1
  TEXT = 2
  SKIP = 3


def parse_srt_lines(lines):
  """Parse the list of subtitle `lines` from .SRT using a state machine, return a cleaned up version."""

  # Remove Windows end lines.
  lines = [line.replace('\r\n', '') for line in lines]
  lines = [line.replace('\n', '') for line in lines]
  # print(lines)

  # State machine to extract the lines.
  phase = PhaseSRT.INDEX
  index = 0
  text = ''
  cleaned_lines = []
  for line in lines:
    # print(f'{phase}: {line} [{index}]')
    if phase == PhaseSRT.INDEX:
      if len(line) > 0:
        line_index = int(line)
        # assert line_index > index or line_index == 0
        index = line_index
        next_phase = PhaseSRT.TIMESTAMP
    elif phase == PhaseSRT.TIMESTAMP:
      assert regexp_timestamp.match(line)
      next_phase = PhaseSRT.TEXT
    elif phase == PhaseSRT.TEXT:
      text, move_on = validate_line_text(cleaned_lines, text, line)
      if move_on:
        next_phase = PhaseSRT.INDEX
    else:
      assert len(line) == 0
    phase = next_phase
  if len(text) > 0:
    validate_line_text(cleaned_lines, text, line)
  return cleaned_lines


def main():
  args = parse_args()

  # Get the list of SRT files.
  path_srt = args.path
  if not path_srt.endswith('.srt'):
    path_srt = os.path.join(path_srt, '*.srt')
  logging.info(f'Looking for .srt files in {path_srt}')

  # Read the SRT files one by one.
  for filename_srt in glob.glob(path_srt):

    # Detect the encoding of the file.
    blob = open(filename_srt, 'rb').read()
    encoding = chardet.detect(blob)
    if encoding and 'encoding' in encoding:
      encoding = encoding['encoding']
    else:
      encoding = 'utf-8'
    logging.info(f'Parsing {filename_srt} as {encoding}')

    # Read the content of the SRT file and clean up the lines.
    with codecs.open(filename_srt, 'r', encoding=encoding) as f:
      lines = f.readlines()
    lines = [unidecode.unidecode(line) for line in lines]
    text = parse_srt_lines(lines)

    # Save the text of the subtitles into a text file.
    filename_txt = filename_srt[:-4] + '.txt'
    with open(filename_txt, 'w') as f:
      f.write('\n'.join(text))


if __name__ == "__main__":
  main()
