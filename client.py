import os

from tun.tun_device import TunDevice
from crypto.encryption import Encryption
from network.transport import Transport
from network.tunnel import Tunnel


HOST = "127.0.0.1"
PORT = 5555


tun = TunDevice("tun0")

try:
    tun.create()
    print("TunnelForge client TUN interface ready")

    os.system("ip addr add 10.10.0.1/24 dev tun0")
    os.system("ip link set tun0 up")

    transport = Transport()
    transport.connect(HOST, PORT)

    client_private = Encryption.generate_key_exchange()
    client_public = Encryption.get_public_key(client_private)
    transport.send(client_public)

    server_public = transport.receive()
    session_key = Encryption.derive_session_key(client_private, server_public)
    crypto = Encryption(session_key)
    print("In-memory session key established on client")
    

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