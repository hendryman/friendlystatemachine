DICT_LLMS = {
	"gpt3": ["gpt-3.5-turbo-instruct"],
	# "gpt4": ["ft:gpt-4o-mini-2024-07-18:improbotics::AUdUeBUK", "gpt-4o-mini"],
	"gpt4": ["gpt-4o-mini"],
	"groq": ["llama-3.3-70b-versatile"], #, "llama-3.1-8b-instant"],
	"ollama": ["dolphin-llama3", "mistral-nemo:12b", "llama3.1:8b", "llama3:70b", "llama3.1:70b"],
	"xai": ["grok-beta"],
	"openrouter": ["thedrummer/rocinante-12b", "thedrummer/unslopnemo-12b", "inflatebot/mn-mag-mell-r1"]
}


def available_llms(family_name: str) -> list[str]:
	return DICT_LLMS[family_name]


def default_llm(family_name: str) -> str:
	return DICT_LLMS[family_name][0]


def split_prompt_into_system_user(prompt: str) -> list[str]:
	lines = prompt.split('\n')
	idx = lines.index('')
	system_prompt = '\n'.join(lines[:idx])
	user_prompt = '\n'.join(lines[idx:])
	return system_prompt, user_prompt


def extract_response(response: str, take_first_line: bool):
	response = response.strip()
	first_line = response.split("\n\n")[0]
	if take_first_line and len(first_line) > 0:
		return first_line
	else:
		return response
