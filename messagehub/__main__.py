import argparse, signal, time, logging

import configargparse, json
import threading
from messagehub.MessageHubServer import MessageHubServer

from osc4py3.as_eventloop import osc_startup, osc_udp_client, osc_send, osc_process, osc_terminate, osc_method, osc_udp_server
from osc4py3 import oscbuildparse, oscmethod

def parse_arguments() -> argparse.Namespace:
    parser = configargparse.ArgumentParser(prog="message-hub", description="Message Hub")
    parser.add_argument("-c", "--config", required=False, is_config_file=True, help="Configuration file path (ini).")

    parser.add_argument("--host"  , type=str, default="0.0.0.0", help="Webserver host address.")
    parser.add_argument("--port"  , type=int, default=8005, help="Webserver port number.")
    
    parser.add_argument("--use_osc_mirror", action="store_true")
    
    parser.add_argument("--meat_host"  , type=str, default="10.10.10.10", help="Meat OSC mirror host address.")
    parser.add_argument("--meat_port"  , type=int, default=5918, help="Meat OSC mirror port number.")

    parser.add_argument("--meat_done_host"  , type=str, default="0.0.0.0", help="Meat done OSC mirror host address.")
    parser.add_argument("--meat_done_port"  , type=int, default=5920, help="Meat done OSC mirror port number.")

    return parser.parse_args()

class OSCMirror(threading.Thread):

    def __init__(self):
        super(OSCMirror, self).__init__()
        osc_startup()

    def add_client(self, client_name, host, ip):
        osc_udp_client(host, ip, client_name)

    def add_server(self, server_name, host, ip):
        osc_udp_server(host, ip, server_name)

    def run(self):
        
        self.running = True
        while(self.running):
            self.process()
            time.sleep(0.1)

    def process(self):
        osc_process()

    def add_handler(self, name, address, callback):
        osc_method(address, callback,  argscheme=oscmethod.OSCARG_ADDRESS + oscmethod.OSCARG_DATA)

    def send_meat_message(self, client_name, jsonData):
        msg = oscbuildparse.OSCMessage("/meat",",s", [json.dumps(jsonData, separators=(',', ':'))])
        osc_send(msg, client_name)
        logging.info(f"sent message: {msg}")

    def send_think_message(self, client_name, data):
        msg = oscbuildparse.OSCMessage("/state",",s", "think")
        osc_send(msg, client_name)
        logging.info(f"sent message: {msg}")

    def stop(self):
        self.running = False
        self.join()
        osc_terminate()


def main():


    args = parse_arguments()

    FORMAT = '%(asctime)s %(levelname)s: %(message)s [%(filename)s:%(lineno)s]'
    logging.basicConfig(format=FORMAT, level=logging.INFO)

    if(args.use_osc_mirror):
        oscMirror = OSCMirror()
        oscMirror.add_client("meat-osc", args.meat_host, args.meat_port)
        oscMirror.add_server("done-osc", args.meat_done_host, args.meat_done_port)

    hub = MessageHubServer(args.host, args.port)

    def user_message_callback(data):
        try:
            if data["av-command"] == 'stt-text-recognition':
                hub.send_message("words-in", {"entity": "user", "text": data["data"]["text"]})
        except Exception as e:
            logging.error(e)

    hub.add_callback("av", lambda data : user_message_callback(data))

    def audio_done_to_words_in(address, data):
        logging.info(f"audio done: {data}")
        hub.send_message("words-in", {"entity" : "Dr. Stanley", "text" : data[0]})

    def osc_message_callback(address, data):
        logging.info(f"received message: {address}, {data}")

    if(args.use_osc_mirror):
        def echo_meat_command(data):
            oscMirror.send_meat_message("meat-osc", data)
            
        def echo_think_command(data):
            oscMirror.send_think_message("meat-osc", data)

        hub.add_callback("meat-command", echo_meat_command )
        hub.add_callback("think", echo_think_command )

        oscMirror.add_handler("done-osc", "/info/audio_done", audio_done_to_words_in )
        oscMirror.add_handler("done-osc", "*", osc_message_callback)
    else:
        pass
        # hub.add_callback("meat-command", echo_meat_command )


    def stop_all():
        if(args.use_osc_mirror):
            oscMirror.stop()
        else:
            pass

    if(args.use_osc_mirror):
        oscMirror.start()

    hub.run()
    stop_all()
    logging.info("Exiting")

if __name__ == "__main__":
    main()
