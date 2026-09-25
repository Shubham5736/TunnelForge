import socket
import os
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import (Ed25519PublicKey)
from tun.tun_device import TunDevice
from crypto.encryption import Encryption
from network.transport import Transport
from network.tunnel import Tunnel

HOST ="0.0.0.0"
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
    # ---------------------------------------------------------
    # Authenticated X25519 handshake
    # ---------------------------------------------------------
    print("\nStarting authenticated handshake...")
    server_identity = Encryption.load_identity_key("keys/server/identity_private.bin")

    server_ephemeral_private = Encryption.generate_key_exchange()
    server_ephemeral_public = Encryption.get_public_key(server_ephemeral_private)

    #Receive client's signed ephemeral key
    client_handshake_payload = transport.receive()
    print("Received authenticated client ephemeral key")

    #Parse client payload
    client_ephemeral_public, client_signature = (
        Encryption.parse_signed_empheral_key(
            client_handshake_payload
        )
    )

    #load trusted client identity
    trusted_client_public_bytes = Path("keys/server/trusted_client_public.bin").read_bytes()

    if len(trusted_client_public_bytes) !=32:
        raise RuntimeError("Invalid trusted client public key")
    
    trusted_client_public = Ed25519PublicKey.from_public_bytes(trusted_client_public_bytes)

    #Verify client BEFORE using its X25519 key
    if not Encryption.verify(
        trusted_client_public,
        client_signature,
        client_ephemeral_public
    ):
        raise RuntimeError("CLIENT IDENTITY VERIFICATION FAILED!!!!")

    #sign server's ephemeral X25519 public key
    server_handshake_payload = (
        Encryption.create_signed_ephemeral_key(
            server_identity, server_ephemeral_public
        )
    )
    
    print("Sending authenticated server ephemeral key...")
    transport.send(server_handshake_payload)

    #derive the session key
    session_key = Encryption.derive_session_key(
        server_ephemeral_private, 
        client_ephemeral_public
    )
    
    crypto = Encryption(session_key)
    print("Authenticated session key established on server")

    # Transport uses the accepted client socket

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