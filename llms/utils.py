def messages_to_prompt_string(messages: list[tuple[str, str]]) -> str:
  """Convert a list of (user, message) into a text prompt."""
  lines = []
  for user, message in messages:
    lines += [f"{user}: {message}"]
  prompt =  "\n".join(lines)
  return prompt
