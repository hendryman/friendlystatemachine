
import socketio
from typing import Callable, Dict
import logging
import json
import uuid
import time

def format_meat_message(
        message: str,
        emotion,       
        azure_style,
        pre_animation,
        post_animation,
        sg_mood,  
        role, 
    ) -> str:
    return json.dumps({
                    "id": str(int(time.time())),
                    "name": "meat",
                    "type": "meat",
                    "channel": "say",
                    "role": role.get(),
                    "text": message.replace("'", '\'').strip(), # TODO: Find a better way to escape quotes
                    "gpt_emotion": "",
                    "gpt_tone": "",
                    "animate": {
                        "pre": pre_animation.get()["animation"],
                        "pre_speed": pre_animation.get()["speed"],
                        "post": post_animation.get()["animation"],
                        "post_speed": post_animation.get()["speed"],
                        "next_state": ""
                    },
                    "azure": azure_style.get(),
                    "emotion": emotion.get(),
                    "sgcom": sg_mood.get()
                })

def format_meat_meatstate(meatstate: str) -> str:
    return json.dumps({
        "id": str(int(time.time())),
        "type": "meat",
        "channel": "state",
        "state": meatstate
    })

def format_meat_audioplayback(
        message : str,
        id : int, 
        emotion,       
        pre_animation,
        post_animation,
        sg_mood,
    ) -> str:
    return json.dumps({
        "id": str(id),
        "type": "meat",
        "text": message,
        "channel": "play",
        "animate": {
            "pre": pre_animation.get()["animation"],
            "pre_speed": pre_animation.get()["speed"],
            "post": post_animation.get()["animation"],
            "post_speed": post_animation.get()["speed"],
            "next_state": ""
        },
        "emotion": emotion.get(),
        "gpt_emotion": "",
        "gpt_tone": "",
        "sgcom": sg_mood.get()
    })

class MessageHubClient:
    MESSAGE_EVENT = "message"
    CUE_EVENT = "cue"

    CHANNEL_ATTRIBUTE = "channel"
    DATA_ATTRIBUTE = "data"
    TURN_ATTRIBUTE = "turn"

    def __init__(self, server_url: str, auto_connect: bool = True):
        self.server_url = server_url
        self.connected = False

        self.callbacks = {}

        self.sio = socketio.Client()
        self.sio.on(self.MESSAGE_EVENT, self._handle_message)
        logging.info(f"Message hub client created for {server_url}")

        if auto_connect:
            self.connect()

    def set_callback(self, channel: str, func: Callable[[str, Dict], None]):
        self.callbacks[channel] = func

    def _handle_message(self, event: Dict):
        try:
            channel = event[self.CHANNEL_ATTRIBUTE]
            data = event[self.DATA_ATTRIBUTE]

            if channel in self.callbacks:
                self.callbacks[channel](channel, data)
        except Exception as ex:
            logging.warning(f"Exception ({ex}) on message handling: {event}")

    def send_message(self, channel: str, data: Dict):
        if not self.connected:
            return
        self.sio.emit(self.MESSAGE_EVENT, {self.CHANNEL_ATTRIBUTE: channel, self.DATA_ATTRIBUTE: data})

    # def send_cue(self, turn: str):
    #     self.send_message(self.CUE_EVENT, {self.TURN_ATTRIBUTE: turn})

    def connect(self, blocking: bool = False):
        logging.info(f"Connecting to message hub at {self.server_url}")
        try:
            self.sio.connect(self.server_url)
            self.connected  = True
        except socketio.exceptions.ConnectionError:
            logging.error("Can't connect to message hub")
            return

        if blocking:
            self.sio.wait()

    def disconnect(self):
        logging.info("Disconnecting from message hub")
        if not self.connected:
            return
        self.sio.disconnect()

