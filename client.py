import os
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import (Ed25519PublicKey)
from tun.tun_device import TunDevice
from crypto.encryption import Encryption
from network.transport import Transport
from network.tunnel import Tunnel


HOST = "192.168.100.2"
PORT = 5555


tun = TunDevice("tun0")

try:
    tun.create()
    print("TunnelForge client TUN interface ready")

    os.system("ip addr add 10.10.0.1/24 dev tun0")
    os.system("ip link set tun0 up")

    transport = Transport()
    transport.connect(HOST, PORT)

    # ---------------------------------------------------------
    # Authenticated X25519 handshake
    # ---------------------------------------------------------
    print("\nStarting authenticated handshake")

    client_identity = Encryption.load_identity_key("keys/client/identity_private.bin")
    client_ephemeral_private = Encryption.generate_key_exchange()
    client_ephemeral_public = Encryption.get_public_key(client_ephemeral_private)

    #sign the ephemeral X25519 public key
    client_handshake_payload = (Encryption.create_signed_ephemeral_key(client_identity, client_ephemeral_public))
    print("Sending authenticted client ephemeral key....")

    #send 32 bytes X25519 public key + 64 bytes Ed25519 signature
    transport.send(client_handshake_payload)

    #receive server's signed ephemeral key
    server_handshake_payload = transport.receive()
    print("Received authenticated server ephemeral key")

    #Parse server payload
    server_ephemeral_public, server_signature = (
        Encryption.parse_signed_empheral_key(server_handshake_payload
        )
    )

    #load trusted server identity
    trusted_server_public_bytes = Path("keys/client/trusted_server_public.bin").read_bytes()

    if len(trusted_server_public_bytes) != 32:
        raise RuntimeError("Invalid trusted server public key")

    trusted_server_public = Ed25519PublicKey.from_public_bytes(trusted_server_public_bytes)

    #Verift the server BEFORE using its X25519 key
    if not Encryption.verify(trusted_server_public, server_signature, server_ephemeral_public):
        raise RuntimeError("SERVER IDENTITY VERIFICATION FAILED")
    print("Server identity verification successful...")

    #Now derive the session key
    session_key = Encryption.derive_session_key(client_ephemeral_private, server_ephemeral_public)

    crypto = Encryption(session_key)

    tunnel = Tunnel(
        tun=tun,
        transport=transport,
        crypto=crypto
    )

    print("TunnelForge client tunnel ready")
    print("Starting bidirectional packet processing...\n")

    tunnel.start()

except ConnectionError as e:
    print(f"Connection error: {e}")

except KeyboardInterrupt:
    print("\nClient interrupted")

finally:
    tunnel.stop() if "tunnel" in locals() else None
    transport.close() if "transport" in locals() else None
    tun.close()

    print("Client resources closed")

    