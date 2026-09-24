import socket
import os

from tun.tun_device import TunDevice
from crypto.encryption import Encryption
from network.transport import Transport
from network.tunnel import Tunnel

HOST ="127.0.0.1"
PORT = 5555

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

server_socket.bind((HOST, PORT))
server_socket.listen(1)

print(f"TunnelForge server listening on {HOST}:{PORT}")

client_socket,client_address = server_socket.accept()
print(f"Client connected: {client_address}")

tun = TunDevice("tun1")
try:
    tun.create()
    print("TunnelForge server TUN interface ready")
    os.system("ip addr add 10.20.0.1/24 dev tun1")
    os.system("ip link set tun1 up")

    transport = Transport(client_socket)
    #AES key as client
    server_private = Encryption.generate_key_exchange()
    server_public = Encryption.get_public_key(server_private)

    client_public = transport.receive()
    transport.send(server_public)

    session_key =Encryption.derive_session_key(server_private,client_public)
    crypto = Encryption(session_key)
    print("In-memory session key established on server")

    # Transport uses the accepted client socket
    transport = Transport(client_socket)
    tunnel = Tunnel(tun=tun, transport=transport, crypto=crypto)
    print("TunnelForge server  tunnel ready")
    print("Starting bidectional packet processing...\n")
    tunnel.start()

except ConnectionError as e:
    print(f"Connection error: {e}")

except KeyboardInterrupt:
    print("\nServer interrupted")

finally:
    tunnel.stop() if "tunnel" in locals() else None
    transport.close() if "transport" in locals() else None
    tun.close()
    client_socket.close()
    server_socket.close()

    print("Server resources closed")