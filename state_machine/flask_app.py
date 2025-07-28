
import time
from datetime import datetime, timedelta
from threading import Thread, Lock
from urllib.parse import unquote
from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_cors import CORS, cross_origin
# from flask import url_for
from flask_socketio import SocketIO, emit
from threading import Thread
from pathlib import Path
import logging
import shutil
import requests

from state_machine import scenemanager
from state_machine.character import StateMachineCharacter


class StatusObject:
    def __init__(self, app, sm, errors = None):
        super().__init__()
        with app.app_context():
            all_bots = sm.model.bots.copy()
            for name, user in sm.model.users.items():
                if isinstance(user, StateMachineCharacter):
                    all_bots[name] = user
            
            automatic_conditions = []
            try:
                for t in sm.states_map[sm.current_state.id].transitions:
                    if t.event == "e_automatic":
                        for c in t.cond.list.items:
                            if not c.is_convention:
                                automatic_conditions.append({
                                    "condition": str(c),
                                    "target": t.target.id
                                })
            except IndexError:
                automatic_conditions = []

            self.status = {
                'scene-manager': {
                    "script-name": sm.script_name,
                    "scene-meta": sm.model.scene_params['meta'],
                    'start-time': datetime.strftime(sm.model.start_time, "%Y-%m-%d %H:%M:%S") if sm.model.start_time else None,
                    'listening': sm.model.listening,
                    'last-scene-change': datetime.strftime(sm.model.last_scene_change, "%Y-%m-%d %H:%M:%S"),
                    'time-since-last-scene-change':  f'{sm.model.time_since_last_scene_change.total_seconds():.1f}s',
                    'output-path': sm.output_path,
                    'state'      : sm.current_state.id,
                    'available-transitions': [t.event for t in sm.states_map[sm.current_state.id].transitions if t.event.startswith("manual_")],
                    'automatic-conditions': automatic_conditions, 
                    'diagram-uri': "/" + str(Path.relative_to(Path(sm.diagram_path), Path(sm.output_path).parent.parent)).replace("\\", "/") + "?v=" + sm.model.svg_version,
                    "current-scene-file": sm.model.scene_params['file_path'].absolute().__str__(),
                    "cached-infered-values": { k: str(v) for k, v in sm.model.inferred_values.items()},
                    "fake_media": sm.model.fake_media,
                    "glitch": sm.model.glitch,
                    "metrics": sm.model.metrics,
                },
                'characters': {
                    name: dict({
                        'full-name': bot.display_name,
                        'behavior' : bot.name,
                        "llm-name" : bot.llm_name,
                        'state'    : bot.current_state.id,
                        "current-behavior-file": sm.behavior_paths[bot.name].absolute().__str__(),
                        'diagram-uri': "/" + str(Path.relative_to(Path(bot.diagram_path), Path(sm.output_path).parent.parent)).replace("\\", "/"),
                        'overrides': [ k for k in bot._overrides.event_sequences.keys()],
                        'persona': bot.persona,
                        'emotion': bot.emotion,
                        'observations': bot.observations,
                        'speech-style': bot.speech_style,
                        'few-shots': bot.few_shots
                    }, **bot.data.json()) for name, bot in all_bots.items()
                },
                'users': {
                    name: dict({
                        'full-name': user.display_name,
                        'emotion'  : user.emotion,
                        'observations': user.observations,
                    }) for name, user in sm.model.users.items() if type(user) is not StateMachineCharacter
                },
                'chat-history': sm.model.chat_history,
                'errors': errors
            }

    def json(self):
        return self.status


class SMThread(Thread):

    def __init__(self, sm_factory, app, status_callback=None, exit_callback=None, *args, **kwargs):
        super().__init__()
        logging.info(f"Creating SMThread")

        self.fr        = 10
        self.last_time = datetime.now()
        self.app = app
        self.sm_factory = sm_factory

        self.args = args
        self.kwargs = kwargs    

        self.status_object = None
        self.status_callback = status_callback
        self.exit_callback = exit_callback
        self.lock = Lock()

        self._setup()
        self._running = False


    def _setup(self):
        self.sm = self.sm_factory(
            exit_callback=self.exit_callback,
            *self.args,
            **self.kwargs
        )

    def start(self):
        self._running = True
        super().start()


    def run(self):
        while self._running:
            if datetime.now() - self.last_time > timedelta(seconds=1/self.fr):
                self.lock.acquire()
                try:
                    self.update()
                finally:
                    self.lock.release()
                if self.status_callback:
                    self.status_callback()
                self.last_time = datetime.now()
            else:
                time.sleep(0.2/self.fr)


    def update(self):
        self.sm.update()

    def send_message(self, message):
        self.sm.msg_in.put(scenemanager.MessageIn(message))

    def get_status_message(self, app):
        if self.lock.acquire(timeout=1/self.fr):
            self.status_object = StatusObject(app, self.sm)
            self.lock.release()
            return self.status_object.json()
        else:
            # logging.error("Failed to acquire lock")
            return self.status_object.json()

    def stop(self):
        logging.info("Stopping SMThread")
        # if 'client' in self.sm.__dict__:
        #     logging.info("Disconnecting client")
        #     self.sm.client.disconnect()

        self._running = False



def run_flask(sm_factory, *args, **kwargs):

    output_root = Path(kwargs['output_root'], kwargs['mode'])
    output_root.mkdir(parents=True, exist_ok=True)

    shutil.copy(Path("state_machine/templates/favicon.ico"), output_root)

    kwargs['output_root'] = output_root

    app = Flask(__name__,
        static_folder=output_root.absolute().__str__(),
    )
    app.config['SERVER_NAME'] = kwargs['server_name']
    app.config['APPLICATION_ROOT'] = "/"
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.config['PREFERRED_URL_SCHEME'] = 'http'
    CORS(app)
    socketio = SocketIO(app, cors_allowed_origins="*")

    logging.getLogger('werkzeug').disabled = True

    sm_thread = None

    def shutdown_callback():
        requests.post(f"http://{kwargs['server_name']}/shutdown")

    @socketio.on('connect')
    def connect():      
        nonlocal sm_thread
        logging.debug('run_flask | Client connected')
        sm_thread  = get_sm()

    @socketio.on('disconnect')
    def disconnect():
        logging.debug('run_flask | Client disconnected')


    def emit_status():
        if sm_thread is not None and sm_thread._running:
            data = sm_thread.get_status_message(app)
            try:
                socketio.emit('stream-status', data)
                pass
            except Exception as e:
                logging.error(f"Error emitting stream status: {e}")
                raise

    def get_sm():
        nonlocal sm_thread
        if sm_thread is None:
            restart_sm_thread()
        return sm_thread

    def restart_sm_thread():
        nonlocal sm_thread
        if sm_thread is not None:
            sm_thread.stop()
            sm_thread.join()

        try:
            x = requests.post("http://127.0.0.1:8005/clear-messages")
            if x.status_code == 200:
                logging.info("Cleared chat history")
            else:
                logging.error(f"Failed to clear chat history: {x.text}")
        except requests.exceptions.ConnectionError as e:
            logging.error(f"Failed to clear chat history: {e}")


        sm_thread = SMThread(
            sm_factory=sm_factory,
            app=app,
            status_callback=lambda: socketio.start_background_task(emit_status),
            exit_callback=shutdown_callback,
            *args, **kwargs
        )
        sm_thread.start()

    @app.route('/')
    @cross_origin()
    def index():
        if kwargs['mode'] == 'test':
            return render_template('index.html', mode=kwargs['mode'])
        elif kwargs['mode'] == 'simulation':
            return render_template('index.html', mode=kwargs['mode'])
        elif kwargs['mode'] == 'perform':
            return render_template('index.html', mode=kwargs['mode'])
        else:
            return render_template('index.html', mode=kwargs['mode'])

    @app.route('/dev')
    @cross_origin()
    def dev():
        return render_template('index_old.html')
    
    @app.route('/td')
    @cross_origin()
    def td():
        return render_template('index_td.html')
    
    @app.route('/shutdown', methods=['POST'])
    @cross_origin()
    def shutdown_server():
        logging.info("Shutting down server")
        raise NotImplementedError("Shutdown not implemented")
        # if sm_thread is not None:
        #     sm_thread.stop()
        #     sm_thread.join(5)
        # if sm_thread.is_alive():
        #     logging.info("Statemachine thread stopped ")
        # else:
        #     logging.error("Statemachine thread failed to stop")

        # func = request.environ.get('werkzeug.server.shutdown')
        # if func is None:
        #     raise RuntimeError('Not running with the Werkzeug Server')
        # else:
        #     func()
        
        # exit(0)


    @app.route('/status', methods=['GET'])
    @cross_origin()
    def status():
        sm_thread = get_sm()
        if sm_thread is None:
            return jsonify({"error": "Scene manager not initialized"})
        return sm_thread.get_status_message(app)
        return jsonify({"error": "Scene manager not initialized"})

    @app.route('/restart', methods=['GET'])
    def restart():
        restart_sm_thread()
        return jsonify({"status": "success"})

    @app.route('/files/<root>/<path:path>')
    @cross_origin()
    def send_file(root, path):
        path = unquote(path)
        return send_from_directory(output_root, path)
    
    @app.route('/scripts/<path:path>')
    @cross_origin()
    def send_script(path):
        path = unquote(path)
        return send_from_directory(Path("state_machine/scripts").absolute().__str__(), path, as_attachment=True)



    # Test with curl -X POST -H "Content-Type: application/json" -d '{"command": "chat", "data" : {"message":"Hello", "user": "web"}}' http://localhost:5000/message
    @app.route('/message', methods=['POST'])
    @cross_origin()
    def messageIn():
        try:
            sm_thread = get_sm()
            data = request.get_json()
            logging.info(f"Received message: {data}")
            sm_thread.send_message(data)
            sm_thread.update()
            return jsonify({"status": "success"})
        except Exception as e:
            logging.error(e)
            shutdown_server()
            return jsonify({"status": "error", "message": str(e)})


    
    logging.info(f"Running flask app on http://{app.config['SERVER_NAME']}")
    try:
        socketio.run(app, debug=False, allow_unsafe_werkzeug=True)
    except TypeError as e:
        socketio.run(app, debug=False)
