# Guides for writing/updating a script

These guides explain how to write new scenes, behaviors, etc. (or how to update them) using the provided YAML structure. The guides describe the types of states, events, and configuration options.

## Contents

- [Directory Structure](#directory-structure)
- [Scenes](#scenes)
  - [Scene Parameters](#scene-parameters)
  - [Characters Section](#characters-section)
  - [Exits Section](#exits-section)
- [Behaviors](#behaviors)
- [Fake Texts](#fake-texts)
- [Few Shots](#few-shots)
- [Overrides](#overrides)
- [Persona](#persona)
- [Set Prompts](#set-prompts)


## Directory Structure

The directory structure for the script folder `friendly-fires` is a follows:

```
└───friendly-fires
    ├───behaviors
    │   └───_behaviors_off
    ├───fake_texts
    ├───few-shots
    ├───overrides
    ├───persona
    ├───scenes
    │   └───_scenes-off
    └───set-prompts
├───
```

Here `friendly-fires` is the script directory, other scripts can be defined in the same root. The script directory contains the following subdirectories:

- `behaviors`: Contains YAML files defining character behaviors. [more...](#behaviors).
- `fake_texts`: Contains JSON files defining fake texts for generating deepfake media. [more...](#fake-texts).
- `few-shots`: Contains plain text files with few-shot prompts for LLM responses. [more...](#few-shots).
- `overrides`: Contains a YAML file defining default override events. [more...](#overrides).
- `persona`: Contains YAML files defining character personas. [more...](#persona).
- `scenes`: Contains YAML files defining scenes. [more...](#scenes).
- `set-prompts`: Contains plain text files with set prompts for extracting dream and hallucination. [more...](#set-prompts).

`_behaviors_off` and `_behaviors_off` contains deprecated YAML files.


## Scenes

The `scenes` directory contains YAML files defining each of the scenes that will build the state-machine for the `SceneManager`. Each scene can specify metadata, characters, and transitions. 

- There must be exactly one entry scene and exactly one final scene.
- There can be no floating scenes, all scenes except the initial scene must be connected by exits.

Here is an example of a scene file with all possible properties:

```yaml
scene:
  name: "My Scene"
  description: "Longer description of the scene."
  initial: False
  final: False
  audio_playback: "001-intro_outro"
  light_cue: "1"
  internal_callbacks:
    - my_callback
  playback: 
   1: "HALLUCINATION"
   2: "HALLUCINATION"
   3: "HALLUCINATION"
characters:
  - display_name: "Wall-E"
    persona_name: "Bot"
    behavior: "b_bot"
    few_shots: "exploration"
    llm_name: "llama3.1:8b"
exits:
  - condition:  complete and has_a_dream
    target   : "s_tells_dream"
  - condition:  complete and not has_a_dream
    target   : "s_does_not_tell_dream"
```

### Scene Parameters

Defines the properties of the scene, as well as what happens when the scene starts.

| Parameter                  | Description                                                                                              | Optional? |  
|----------------------------|----------------------------------------------------------------------------------------------------------|----------|
| `scene.name`               | The human readable name of the scene.                                                                    | No       |
| `scene.description`        | A longer description of the scene for reference or logging purposes.                                     | No       |
| `scene.initial`            | A boolean indicating if this scene is the starting point.                                                | No       |
| `scene.final`              | A boolean indicating if this scene is the endpoint. A final scene cannot have `exits`.                                           | No       |
| |||
| `scene.audio_playback`     | The identifier for audio playback associated with this scene (default none).                                            | Yes      |
| `scene.light_cue`          | A lighting cue identifier, typically used for stage lighting in simulations or visual representations (must be integer, default none).   | Yes      |
| `scene.internal_callbacks` | A list of internal callback function names to be executed during the scene (must be members of `SceneManager`; default none).                              | Yes      |
| `scene.playback`           | A dictionary defining media playback (e.g., hallucinations) triggered during the scene (default: none). The 3 keys `1`, `2`, `3` correspond to 3 screens.                 | Yes      |
---

### Characters Section

Defines a list of participants in the scene (note that it starts with `-`). It is possible to specify zero or more characters in a scene.

| Parameter         | Description                                                                                  | Example Value           | Optional? |
|-------------------|----------------------------------------------------------------------------------------------|-------------------------|----------|
| `display_name`    | The character's unique identifier in the scene, used for dialogue. Several persona can share the same `display_name`.
| `"Wall-E"`                 | No       |
| `persona_name`    | The character's persona and unique identified in the scene, used for system prompt. Each persona is a bot.
| `"Bot"`                 | No       |
| `behavior`        | The behavior file to load for this character. This must be a valid behavior file in the `behaviors` directory.                                               | `"b_bot"`               | No       |
| `few_shots`       | The name of the few-shot prompt file linked to this character (default: none).                               | `"exploration"`         | Yes      |
| `llm_name`        | The name of the large language model to use for this character's responses (default: "gpt-4o-mini").                  | `"llama3.1:8b"`         | Yes      |
---

### Exits Section

Specifies a list of transitions out of the current scene, including the conditions required for each transition and the target scene.

| Parameter   | Description                                                                                       | Example Value                  | Optional? |
|-------------|---------------------------------------------------------------------------------------------------|--------------------------------|----------|
| `condition` | A logical condition that must be satisfied for this transition to occur.                          | `"complete and has_a_dream"`  | No        |
| `target`    | The name of the target scene to transition to if the condition is met (must name a scene in the same script).                            | `"s_tells_dream"`             | No        |

More on the **`condition`**:
- A logical condition that must be satisfied for the transition to occur. See the `python-statemachine` [documentation](https://python-statemachine.readthedocs.io/en/latest/guards.html) documentation for more information on defining conditions.
- Conditions can be set to `null` which is equivalent to `wait_for_manual` (i.e. Operators can only be triggered manually by the operator).
---

## Behaviors

The `behaviors` directory defines YAML files for character behaviors. For more information, see the [behavior documentation](BEHAVIORS.md) documentation.

## Fake Texts

This folder can contain `static_fake_texts.json`. This file a dictionary of texts that can be used to generate media and responses in scenes. The texts can be user to generate deepfake video and audio.

Example:

```json
{
    "DEEPFAKE_VIDEO_DONT_YOU_REMEMBER" : {
        "id"    : 101,
        "text"  : "Don't you remember?",
        "audio" : "user",
        "video" : "user"
    },
}
```

- `id`: Unique identifier for the text.
- `text`: The text to used.
- `audio`: The audio source. Can be `'user'` or `'stanley'`.
- `video`: The video source. Can be `'user'`, `'stanley'` or `false`.


If the fake text key is preceded with `DEEPFAKE_VIDEO_`, `DEEPFAKE_AUDIO_` or `STANLEY_AUDIO_`, the text will be available for use in behavior-driven events via a placeholder matching its key preceded by `'_'` (e.g `_DEEPFAKE_VIDEO_DONT_YOU_REMEMBER`).


## Few Shots

Few-shot prompts in the `few-shots` directory guide specific parts of the dialogue or action generation. These are plain text files that are added to the [behavior](BEHAVIORS.md) prompts (see `_FEW_SHOTS`) to give examples of responses given the context of a scene or task.

These files contain several examples of dialogue, preceded by a line saying that it is an example. The example itself is delimited by `Beginning of transcript` and `End of transcript`, like in the example below:

```
Example of dialogue:

--- Beginning of transcript ---

[some dialogue]

--- End of transcript ---
```

They are loaded dynamically and linked to characters or actions based on scene definitions.

## Overrides

This folder can contain a `default_overrides.yaml` file that can be used to set a default lists of override events that will be available in any behavior. For more information on defining evens, see the [BEHAVIORS.md](BEHAVIORS.md) documentation.

Example:

```yaml
childhood:
  speak: I wish I knew my mother.
  emotion: sad
rephrase:
  speak: Can you just rephrase what you just said?
  emotion: neutral
```

## Persona

The `persona` directory contains definitions for character personas. Each persona defines the tone, style, and personality traits that influence how a character communicates. These files are loaded and assigned to characters in the scenes, and added to the system prompt (see `_PERSONA`).


## Set Prompts

The `set-prompts` directory contains documentation about the custom prompts, which can be used to run the `grok-beta` LLM on the `_CHAT_HISTORY` to analyse it at each step. They can be used for two purposes:
1. Create a `TRUE`/`FALSE` exit condition for the scene (e.g., `has_a_dream`).
2. To generate text that will fill in the other prompts. For example: `derive_issues` is used to fill in placeholder `_ISSUES`, and `derive_hallucination` is used to fill in placeholder `_HALLUCINATION` for behaviours `deepfake_hallucination`, and to be shared with the deep fake generator.

You can look at file `prompt_has_a_dream` to get inspiration to add a new boolean condition to a scene. That prompt will be automatically loaded and called when the program enters the scene that mentions it. It will also show up in the visual interface as a `true`/`false` flag (otherwise is shows as `null`).

```yaml
name: has_a_dream
llm_name: grok-beta
return_type: bool
prompt: |-
  _CHAT_HISTORY

  Did the patient describe a dream they had?
  If yes answer `TRUE`
  If no answer `FALSE`
```
