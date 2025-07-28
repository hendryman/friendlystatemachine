from collections import deque, defaultdict
from datetime import datetime
from typing import Dict
import logging
import json

from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO
import socketio


class MessageHubServer:

    def __init__(self, host: str, port: int, max_messages: int = 100):
        self.host = host
        self.callbacks = defaultdict(list)
        self.port = port

        self.app = Flask(__name__)
        self.app.logger.setLevel(level=logging.INFO)

        self.socketio = SocketIO(self.app)

        self.messages = deque(maxlen=max_messages)

        self.sioclient = socketio.Client()

        self.setup_routes()
        self.setup_socketio()

        logging.info(f"MessageHubServer running on {host}:{port}")

    def send_message(self, channel: str, data: Dict):
        try:
            self.sioclient.connect(f"http://127.0.0.1:{self.port}")
        except Exception as e:
            logging.error(e)
        try:
            self.sioclient.emit("message", {"channel": channel, "data": json.dumps(data)})
        except Exception as e:
            logging.error(e)



    def add_callback(self, channel, func):
        self.callbacks[channel].append(func)

    def setup_routes(self):
        @self.app.route("/")
        def index():
            return render_template("index.html")

        @self.app.route("/test")
        def test():
            return render_template("test.html")

        @self.app.route("/message-log")
        def message_log():
            return render_template("message-log.html")


        @self.app.route("/control")
        def control():
            return render_template("control.html")

        @self.app.route("/clear-messages", methods=["POST"])
        def clear_messages():
            self.messages.clear()
            return jsonify(success=True)

        @self.app.route("/get-messages")
        def get_messages():
            messages_list = list(reversed([{"channel": msg["channel"], "data": json.dumps(msg["data"]), "timestamp": msg["timestamp"]}
                                           for msg in self.messages]))
            return jsonify(messages=messages_list)


        @self.app.route("/get-messages-filtered/<channel_list>")
        def get_messages_filtered(channel_list):

            channels = channel_list.split(",")
            messages_list = list(reversed([{"channel": msg["channel"], "data": json.dumps(msg["data"]), "timestamp": msg["timestamp"]}
                                           for msg in self.messages if msg['channel'] in channels]))
            return jsonify(messages=messages_list)


    def setup_socketio(self):
        @self.socketio.on("connect")
        def handle_connect():
            self.app.logger.info("client connected")

        @self.socketio.on("message")
        def handle_message(message):
            try:
                channel = message['channel']
                data = json.loads(message['data'])
            except (json.JSONDecodeError, TypeError, KeyError):
                self.app.logger.warn(f"JSON Decvvvode Error: channel: '{message}'")
                return
            logging.info(f"Received message: {channel} - {data}")
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            message_with_timestamp = {"channel": channel, "data": data, "timestamp": timestamp}
            self.messages.append(message_with_timestamp)

            if(channel in self.callbacks):
                for func in self.callbacks[channel]:
                    func(data)

            self.socketio.emit("message", message)

    def run(self):
        try:
            self.socketio.run(self.app, host=self.host, port=self.port, debug=True, allow_unsafe_werkzeug=True,use_reloader=False)
        except TypeError as e:
            self.socketio.run(self.app, host=self.host, port=self.port, debug=True,use_reloader=False)


