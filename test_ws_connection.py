import asyncio
import websockets
import json
import sys

async def test_connection():
    uri = "ws://127.0.0.1:5000/ws"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected!")
            
            # Wait for initial messages
            try:
                while True:
                    message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(message)
                    msg_type = data.get('type')
                    print(f"Received message type: {msg_type}")
                    
                    if msg_type == 'event' and data.get('event') == 'status':
                        print("Status received")
                    elif msg_type == 'event' and data.get('event') == 'reset_session':
                        print("Reset session received")
                        
            except asyncio.TimeoutError:
                print("Timeout waiting for message")
            except websockets.exceptions.ConnectionClosed as e:
                print(f"Connection closed: {e}")
                
    except Exception as e:
        print(f"Failed to connect: {e!r}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_connection())
