import socketio

# Create a Socket.IO client
sio = socketio.Client()

# Event to handle connection
@sio.event
def connect():
    print('Connected to server')
    print('Session ID:', sio.sid)

# Event to handle disconnection
@sio.event
def disconnect():
    print('Disconnected from server')

# Event to handle custom stream-status data
@sio.on('stream-status')
def on_stream_status(data):
    print('Received stream-status data:', data)
    # Add your custom logic here to handle the data

# Main function to connect to the server
def main():
    # Replace with your server's URL and port
    socket_address = 'http://127.0.0.1:5000'
    
    try:
        # Connect to the server
        sio.connect(socket_address)
        print('Socket.IO client connected.')
        
        # Keep the connection open
        sio.wait()
    except Exception as e:
        print(f"Failed to connect: {e}")

if __name__ == "__main__":
    main()
