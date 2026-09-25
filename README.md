# TunnelForge

TunnelForge is an educational encrypted network-tunneling project
written in Python.

The project demonstrates how a VPN-like tunnel can be built from
lower-level components:

-   Linux TUN interfaces for capturing and injecting IP packets
-   A transport layer for moving tunnel data between client and server
-   Ephemeral X25519 key exchange
-   HKDF-SHA256 session-key derivation
-   Persistent Ed25519 identity keys
-   Trusted-peer identity verification
-   Signed ephemeral keys to authenticate the key exchange
-   AES-256-GCM authenticated encryption for tunnel traffic
-   Bidirectional packet forwarding between the TUN interface and the
    network transport

> **Current implementation:** TunnelForge uses **TCP** as its transport.
> UDP transport is planned as a later architectural stage and is not
> part of the code documented here.

This project is intended for learning, experimentation, protocol design,
Linux networking, and cryptographic engineering. It is **not
production-ready VPN software**.

------------------------------------------------------------------------

## 1. Architecture

At a high level, TunnelForge works like this:

``` text
                     TunnelForge
              =========================

 Client machine                              Server machine
 ┌───────────────┐                           ┌───────────────┐
 │ Application   │                           │ Application   │
 └───────┬───────┘                           └───────┬───────┘
         │                                           │
         ▼                                           ▼
 ┌───────────────┐                           ┌───────────────┐
 │    tun0       │                           │    tun1       │
 │ 10.10.0.1/24  │                           │ 10.20.0.1/24  │
 └───────┬───────┘                           └───────┬───────┘
         │                                           │
         ▼                                           ▲
 ┌───────────────────────────────────────────────────────────┐
 │                         Tunnel                             │
 │                                                           │
 │  TUN → read packet → AES-GCM encrypt → Transport →       │
 │                                                           │
 │  TUN ← write packet ← AES-GCM decrypt ← Transport ←       │
 └───────────────────────────────────────────────────────────┘
                         │
                         │ TCP :5555
                         │
                  ┌──────▼──────┐
                  │ TCP socket  │
                  └─────────────┘
```

The `Tunnel` class runs two directions concurrently:

1.  Read an IP packet from the TUN interface, encrypt it, and send it
    through the transport.
2.  Receive an encrypted packet from the transport, decrypt it, and
    write the resulting IP packet to the TUN interface.

The implementation uses two threads for these directions.

------------------------------------------------------------------------

## 2. Project Structure

The code is organized into separate modules:

``` text
TunnelForge/
├── client.py
├── server.py
│
├── tun/
│   └── tun_device.py
│
├── network/
│   ├── transport.py
│   └── tunnel.py
│
├── crypto/
│   └── encryption.py
│
├── keys/
│   ├── client/
│   │   ├── identity_private.bin
│   │   ├── identity_public.bin
│   │   └── trusted_server_public.bin
│   │
│   └── server/
│       ├── identity_private.bin
│       ├── identity_public.bin
│       └── trusted_client_public.bin
│
└── README.md
```

Python package directories should contain `__init__.py` files if your
local project requires regular package imports.

------------------------------------------------------------------------

## 3. Main Components

### 3.1 `tun/tun_device.py`

`TunDevice` provides a small wrapper around Linux's `/dev/net/tun`.

It:

-   Opens `/dev/net/tun`
-   Creates a TUN interface
-   Uses `IFF_TUN | IFF_NO_PI`
-   Reads raw IP packets
-   Writes raw IP packets
-   Closes the TUN file descriptor

The implementation reads up to 65535 bytes from the TUN device.

Example interface usage:

``` text
tun0 → client
tun1 → server
```

The current client assigns:

``` text
10.10.0.1/24
```

and the server assigns:

``` text
10.20.0.1/24
```

------------------------------------------------------------------------

### 3.2 `network/transport.py`

The current transport layer is TCP.

It:

-   Creates an IPv4 TCP socket
-   Connects the client to the server
-   Sends data using a 4-byte big-endian length prefix
-   Receives exactly the requested number of bytes
-   Reconstructs complete application messages from the TCP byte stream
-   Closes the socket

The current framing is:

``` text
┌──────────────┬──────────────────────┐
│ 4-byte size  │      payload         │
└──────────────┴──────────────────────┘
```

The length prefix is necessary because TCP is a byte stream and does not
preserve application message boundaries.

This is intentionally separated from the `Tunnel` class so the transport
can later be replaced by another mechanism.

------------------------------------------------------------------------

### 3.3 `network/tunnel.py`

`Tunnel` connects the TUN device, transport, and cryptographic layer.

The outbound path is:

``` text
TUN packet
   ↓
AES-GCM encryption
   ↓
Transport.send()
   ↓
TCP
```

The inbound path is:

``` text
TCP
   ↓
Transport.receive()
   ↓
AES-GCM decryption
   ↓
TUN packet
```

Two threads are used:

``` text
tun_to_network()
network_to_tun()
```

This allows packets to travel in both directions simultaneously.

------------------------------------------------------------------------

### 3.4 `crypto/encryption.py`

The cryptographic layer contains the project's crypto logic.

It uses:

  Purpose                   Algorithm
  ------------------------- --------------------
  Data encryption           AES-GCM
  Ephemeral key exchange    X25519
  Session-key derivation    HKDF-SHA256
  Long-term identity        Ed25519
  Identity authentication   Ed25519 signatures

#### Session key

The client and server generate fresh X25519 ephemeral key pairs.

The X25519 shared secret is then passed through:

``` text
HKDF-SHA256
```

with:

``` text
length = 32 bytes
info = "TunnelForge-v1"
```

The result is used as the AES-GCM session key.

Both sides independently derive the same session key.

#### Packet encryption

Each packet is encrypted with AES-GCM using a fresh 12-byte nonce.

The transmitted encrypted value is:

``` text
12-byte nonce || AES-GCM ciphertext
```

AES-GCM provides both confidentiality and integrity/authentication for
the encrypted packet.

------------------------------------------------------------------------

## 4. Authenticated Handshake

TunnelForge does more than perform unauthenticated X25519 key exchange.

The current design uses persistent Ed25519 identity keys to authenticate
ephemeral X25519 keys.

### Client side

The client:

1.  Loads its persistent Ed25519 identity private key.
2.  Generates a fresh X25519 ephemeral private key.
3.  Derives the X25519 public key.
4.  Signs the ephemeral X25519 public key with its Ed25519 identity key.
5.  Sends:

``` text
X25519 public key (32 bytes)
+
Ed25519 signature (64 bytes)
```

Total:

``` text
96 bytes
```

### Server side

The server:

1.  Receives the client's 96-byte payload.
2.  Splits it into the X25519 public key and Ed25519 signature.
3.  Loads the trusted client Ed25519 public key.
4.  Verifies the signature.
5.  Only after successful verification uses the client's X25519 public
    key.

The server then performs the same operation for its own ephemeral key:

``` text
Server X25519 public key
        +
Server Ed25519 signature
```

The client verifies the server using its trusted server public key.

Only after identity verification do both sides derive the session key.

### Trust model

The client stores the server's trusted identity public key:

``` text
keys/client/trusted_server_public.bin
```

The server stores the client's trusted identity public key:

``` text
keys/server/trusted_client_public.bin
```

This provides a basic static trust relationship suitable for the
educational project.

------------------------------------------------------------------------

## 5. Requirements

Recommended environment:

-   Linux
-   Python 3
-   Root/sudo privileges
-   `/dev/net/tun`
-   `iproute2`
-   Python `cryptography` package

Parrot OS is suitable for running the project.

Install the system networking tools:

``` bash
sudo apt update
sudo apt install -y iproute2 python3 python3-pip python3-venv
```

------------------------------------------------------------------------

## 6. Clone and Enter the Repository

``` bash
git clone <YOUR-GITHUB-REPOSITORY-URL>
cd TunnelForge
```

If you are working from an existing local repository:

``` bash
cd /path/to/TunnelForge
```

------------------------------------------------------------------------

## 7. Create a Python Virtual Environment

Creating a virtual environment is recommended:

``` bash
python3 -m venv .venv
source .venv/bin/activate
```

Upgrade pip:

``` bash
python -m pip install --upgrade pip
```

Install the cryptography dependency:

``` bash
pip install cryptography
```

You can verify it with:

``` bash
python -c "import cryptography; print(cryptography.__version__)"
```

------------------------------------------------------------------------

## 8. Generate the Identity Keys

TunnelForge requires persistent Ed25519 identity keys for both peers.

The `Encryption` module contains the key-generation and persistence
functionality.

You can generate the keys using the project's crypto test code:

``` bash
python crypto/encryption.py
```

The module's standalone test creates:

``` text
keys/client/identity_private.bin
keys/client/identity_public.bin

keys/server/identity_private.bin
keys/server/identity_public.bin
```

The private keys are stored with restrictive permissions:

``` text
0600
```

Public keys are stored with:

``` text
0644
```

### Important

Do not commit private identity keys to GitHub.

Add the following to `.gitignore`:

``` gitignore
keys/*/identity_private.bin
```

If this is a public repository, it is also safer to generate the
identity keys locally instead of publishing any real private key
material.

------------------------------------------------------------------------

## 9. Configure Trusted Peer Keys

The client must trust the server's public identity key.

Copy:

``` bash
cp keys/server/identity_public.bin \
   keys/client/trusted_server_public.bin
```

The server must trust the client's public identity key.

Copy:

``` bash
cp keys/client/identity_public.bin \
   keys/server/trusted_client_public.bin
```

The resulting structure should be:

``` text
keys/
├── client/
│   ├── identity_private.bin
│   ├── identity_public.bin
│   └── trusted_server_public.bin
│
└── server/
    ├── identity_private.bin
    ├── identity_public.bin
    └── trusted_client_public.bin
```

Verify the key sizes:

``` bash
wc -c keys/client/*.bin
wc -c keys/server/*.bin
```

Expected public/private Ed25519 raw key sizes are 32 bytes.

------------------------------------------------------------------------

## 10. Configure the Server Address

The client currently connects to:

``` text
192.168.100.2:5555
```

This is defined in `client.py`:

``` python
HOST = "192.168.100.2"
PORT = 5555
```

Change `HOST` to the IP address of the machine running `server.py`.

The server listens on:

``` text
0.0.0.0:5555
```

The port can be changed in both files, but the values must match.

------------------------------------------------------------------------

## 11. Firewall

If a firewall is enabled on the server, allow TCP port `5555`.

For example, with UFW:

``` bash
sudo ufw allow 5555/tcp
```

Check:

``` bash
sudo ufw status
```

Only expose the port to networks where you actually intend to run the
experiment.

------------------------------------------------------------------------

# 12. Run the Server

Start the server first:

``` bash
sudo python3 server.py
```

Expected output includes:

``` text
TunnelForge server listening on 0.0.0.0:5555
```

The server then waits for the client.

When the client connects, it creates:

``` text
tun1
```

and assigns:

``` text
10.20.0.1/24
```

------------------------------------------------------------------------

# 13. Run the Client

In another terminal:

``` bash
sudo python3 client.py
```

The client creates:

``` text
tun0
```

and assigns:

``` text
10.10.0.1/24
```

The client then connects to the configured server:

``` text
192.168.100.2:5555
```

------------------------------------------------------------------------

# 14. Expected Handshake

A successful run should show messages similar to:

``` text
TunnelForge client TUN interface ready

Starting authenticated handshake
Sending authenticted client ephemeral key....
Received authenticated server ephemeral key
Server identity verification successful...
TunnelForge client tunnel ready
Starting bidirectional packet processing...
```

On the server:

``` text
TunnelForge server listening on 0.0.0.0:5555
Client connected: ...
TunnelForge server TUN interface ready

Starting authenticated handshake...
Received authenticated client ephemeral key
Sending authenticated server ephemeral key...
Authenticated session key established on server
TunnelForge server tunnel ready
Starting bidectional packet processing...
```

The exact output may differ slightly because it depends on the current
source formatting.

------------------------------------------------------------------------

# 15. Verify the TUN Interfaces

After starting both sides:

``` bash
ip addr show tun0
```

and:

``` bash
ip addr show tun1
```

The client should have:

``` text
10.10.0.1/24
```

The server should have:

``` text
10.20.0.1/24
```

Also check:

``` bash
ip link show tun0
ip link show tun1
```

------------------------------------------------------------------------

# 16. Test the TUN Device Independently

Before debugging the complete tunnel, you can test the TUN wrapper
itself.

Run:

``` bash
sudo python3 tun/tun_device.py
```

It should create `tun0` and wait for a packet:

``` text
TUN interface 'tun0' created
TUN interface created
Waiting for a packet...
```

In another terminal, inspect the interface:

``` bash
ip addr show tun0
```

The standalone test reads one packet and writes it back.

Stop the test with:

``` text
Ctrl+C
```

------------------------------------------------------------------------

# 17. Test the Cryptographic Module

Run:

``` bash
python3 crypto/encryption.py
```

The standalone crypto tests cover several important properties.

### X25519

It generates client and server ephemeral keys and verifies that both
sides derive the same session key.

Expected result:

``` text
Session key exchange successful
```

### AES-GCM

The test encrypts data with the derived session key and decrypts it with
the other side's derived session key.

Expected result:

``` text
Encryption test successful
```

### Persistent identity keys

The test generates/loads persistent Ed25519 identity keys and verifies
identity continuity.

### Trusted identities

It checks that:

``` text
client trusted_server_public == server identity_public
```

and:

``` text
server trusted_client_public == client identity_public
```

### Ed25519 signatures

It verifies that a valid signature is accepted and modified data is
rejected.

### Signed ephemeral keys

It verifies the 96-byte:

``` text
32-byte X25519 public key
+
64-byte Ed25519 signature
```

payload.

It also modifies the ephemeral public key and confirms that signature
verification fails.

Expected result:

``` text
MITM tampering correctly rejected
Step 3.5 test PASSED
```

------------------------------------------------------------------------

# 18. Test the Complete Tunnel

Once both client and server are running, verify that the interfaces
exist:

``` bash
ip addr show tun0
ip addr show tun1
```

Check the routes:

``` bash
ip route
```

Then test connectivity according to the routing topology you have
configured.

For the project's namespace-based testing environment, inspect the
namespaces:

``` bash
ip netns list
```

If your test setup contains:

``` text
tf-client
tf-server
```

you can inspect their addresses and routes:

``` bash
sudo ip netns exec tf-client ip addr
sudo ip netns exec tf-server ip addr
```

and:

``` bash
sudo ip netns exec tf-client ip route
sudo ip netns exec tf-server ip route
```

------------------------------------------------------------------------

# 19. Ping Test

A basic tunnel validation is:

``` bash
ping <remote-tunnel-address>
```

For namespace-based testing, use:

``` bash
sudo ip netns exec tf-client ping <server-address>
```

and, where appropriate:

``` bash
sudo ip netns exec tf-server ping <client-address>
```

The important point is that the packet should enter the client TUN
interface, travel through the encrypted TunnelForge transport, be
decrypted on the server, and be injected into the server TUN interface.

------------------------------------------------------------------------

# 20. Verify That Traffic Is Actually Traversing the Tunnel

Do not rely only on a successful `ping`.

A successful test should establish the packet path:

``` text
Application
    ↓
Client network namespace
    ↓
tun0
    ↓
Tunnel.tun_to_network()
    ↓
AES-GCM
    ↓
TCP transport
    ↓
Server transport
    ↓
AES-GCM decrypt
    ↓
tun1
    ↓
Server network namespace
```

Check the TUN interfaces:

``` bash
ip -s link show tun0
ip -s link show tun1
```

Generate traffic and check whether packet/byte counters increase.

------------------------------------------------------------------------

# 21. Test Real Application Traffic

After ping works, test actual application traffic.

For example, start a simple HTTP server on one side:

``` bash
python3 -m http.server 8000
```

Then connect from the other side:

``` bash
curl http://<remote-address>:8000
```

You can also test SSH if an SSH service is available:

``` bash
ssh user@<remote-address>
```

The goal is to verify that the tunnel carries normal application
traffic, not just ICMP.

------------------------------------------------------------------------

# 22. Inspect the Encrypted Transport With Wireshark

Wireshark can be used to inspect the physical/network transport.

For the current implementation, the tunnel transport is TCP:

``` text
TCP port 5555
```

Capture traffic on the appropriate physical/network interface.

A useful Wireshark display filter is:

``` text
tcp.port == 5555
```

You should see the TCP transport carrying TunnelForge data.

The encrypted packet contents should not appear as readable original
IP/application payloads.

The handshake also has recognizable structural properties:

``` text
96-byte signed ephemeral payload
```

while application packets are encrypted with AES-GCM.

------------------------------------------------------------------------

# 23. Useful Linux Debugging Commands

### Check listening sockets

``` bash
sudo ss -lntp
```

Look for:

``` text
:5555
```

### Check the server port

``` bash
sudo ss -lntp | grep 5555
```

### Check TUN interfaces

``` bash
ip link show
```

or:

``` bash
ip addr
```

### Check routes

``` bash
ip route
```

### Check network namespaces

``` bash
ip netns list
```

### Inspect namespace interfaces

``` bash
sudo ip netns exec tf-client ip addr
sudo ip netns exec tf-server ip addr
```

### Inspect namespace routes

``` bash
sudo ip netns exec tf-client ip route
sudo ip netns exec tf-server ip route
```

### Check which process owns `/dev/net/tun`

``` bash
sudo lsof /dev/net/tun
```

This is useful when you receive an error indicating that the TUN device
is busy.

------------------------------------------------------------------------

# 24. Common Problems

## PermissionError opening `/dev/net/tun`

Run the client/server with root privileges:

``` bash
sudo python3 client.py
```

and:

``` bash
sudo python3 server.py
```

Check that the TUN device exists:

``` bash
ls -l /dev/net/tun
```

------------------------------------------------------------------------

## `Address already in use`

Check for an existing process:

``` bash
sudo ss -lntp | grep 5555
```

Stop the old server process before starting a new one.

------------------------------------------------------------------------

## TUN interface already exists

Check:

``` bash
ip link show tun0
ip link show tun1
```

Remove a stale interface if necessary:

``` bash
sudo ip link delete tun0
```

or:

``` bash
sudo ip link delete tun1
```

Only remove an interface if it belongs to this experiment.

------------------------------------------------------------------------

## `Connection refused`

Make sure the server is running first:

``` bash
sudo python3 server.py
```

Then verify:

``` bash
sudo ss -lntp | grep 5555
```

Also verify that the client's `HOST` value points to the correct server
IP.

------------------------------------------------------------------------

## Identity verification failure

If you see:

``` text
SERVER IDENTITY VERIFICATION FAILED
```

check:

``` bash
cmp \
  keys/client/trusted_server_public.bin \
  keys/server/identity_public.bin
```

The command should produce no output when the files match.

For the client identity:

``` bash
cmp \
  keys/server/trusted_client_public.bin \
  keys/client/identity_public.bin
```

If the identity keys were regenerated, the trusted public-key files must
also be updated.

------------------------------------------------------------------------

## `Invalid trusted ... public key`

Check the file size:

``` bash
wc -c keys/client/trusted_server_public.bin
wc -c keys/server/trusted_client_public.bin
```

Each Ed25519 public key must be 32 bytes in this implementation.

------------------------------------------------------------------------

## No ping response

First check:

``` bash
ip addr
ip route
```

Then check both TUN interfaces:

``` bash
ip addr show tun0
ip addr show tun1
```

For namespace testing:

``` bash
sudo ip netns exec tf-client ip route
sudo ip netns exec tf-server ip route
```

Also verify that the TunnelForge processes are still running and that
the TCP session remains established:

``` bash
ss -tn
```

A successful application-level ping requires correct routing in addition
to a successful encrypted tunnel.

------------------------------------------------------------------------

# 25. Security Design

TunnelForge currently demonstrates several important security concepts.

### Confidentiality

Tunnel packets are encrypted using AES-GCM.

### Integrity and authentication of encrypted packets

AES-GCM provides authenticated encryption. Modified ciphertext should
fail decryption.

### Forward session separation

The tunnel uses fresh X25519 ephemeral keys for session establishment.

### Peer authentication

Persistent Ed25519 identity keys authenticate the ephemeral X25519
public keys.

### Trusted-peer model

The client and server explicitly store trusted peer public keys.

### Key derivation

The raw X25519 shared secret is passed through HKDF-SHA256 rather than
being used directly as the AES key.

------------------------------------------------------------------------

# 26. Current Security/Protocol Limitations

TunnelForge is an educational implementation and still has important
limitations.

## TCP transport

The current implementation runs the encrypted tunnel over TCP.

This can cause TCP-over-TCP performance problems when the tunnel itself
carries TCP connections.

A later project stage is intended to move the transport to UDP.

## Handshake replay protection

The current signed handshake authenticates the ephemeral public key, but
the signature is currently over the ephemeral public key itself.

A future improvement is to bind the signature to a fresh handshake nonce
so an old valid signed payload cannot simply be replayed in a new
handshake.

## Packet replay/reordering protection

The current tunnel does not implement an independent packet
sequence-number/window mechanism for encrypted data packets.

A later stage is planned to add replay and reordering protection,
particularly for UDP.

## Automatic key rotation

The current tunnel establishes a session key at handshake time but does
not automatically rekey during a long-running session.

A later stage is planned for automatic key rotation.

## Multi-peer support

The current server accepts a single TCP client.

Multi-peer support is a future architectural stage.

## Connection persistence/roaming

The current implementation does not provide roaming or automatic
connection persistence.

## MTU/fragmentation handling

The current implementation reads up to 65535 bytes from the TUN device,
but it does not implement a complete VPN-style MTU/fragmentation
strategy.

This becomes especially important when the transport is moved to UDP.

------------------------------------------------------------------------

# 27. Planned Development Roadmap

The project has been developed in stages.

### Stage 1 --- Basic encrypted tunnel

Initial transport and encryption concepts.

### Stage 2 --- TUN-based tunneling

Move from application-level test data to raw IP packets through Linux
TUN interfaces.

### Stage 3 --- Trustworthy handshake

Add:

-   Persistent Ed25519 identities
-   Ephemeral X25519 keys
-   Signed ephemeral keys
-   Trusted peer public keys
-   Signature verification before using the peer's ephemeral key

### Stage 4 --- Network/application validation

Validate:

-   TUN routing
-   Ping
-   Real application traffic
-   Wireshark visibility
-   Encrypted transport

### Stage 5 --- UDP transport

Planned changes include:

-   Replace TCP sockets with UDP sockets
-   Remove TCP length-prefix framing
-   Preserve complete datagram boundaries
-   Reconsider packet size and MTU
-   Re-run the authenticated handshake over UDP
-   Re-test the tunnel with ping and real application traffic

### Stage 6 --- Automatic key rotation

Planned periodic/threshold-based session rekeying.

### Stage 7 --- Replay and reordering protection

Planned sequence numbers and replay-window logic for encrypted data
packets.

### Stage 8 --- Multi-peer support

Planned server architecture for multiple simultaneous peers.

### Stage 9 --- Roaming and connection persistence

Planned handling of changing network paths and persistent sessions.

------------------------------------------------------------------------

# 28. Recommended `.gitignore`

Do not publish private identity keys.

Example:

``` gitignore
__pycache__/
*.py[cod]

.venv/
venv/

keys/*/identity_private.bin

*.pcap
*.pcapng

.idea/
.vscode/
```

If you want the repository to include example/public test keys, clearly
label them as disposable test keys.

------------------------------------------------------------------------

# 29. Development Notes

TunnelForge intentionally keeps cryptographic operations in one module:

``` text
crypto/encryption.py
```

The networking logic is separated into:

``` text
network/transport.py
network/tunnel.py
```

and TUN handling is isolated in:

``` text
tun/tun_device.py
```

This modular design makes it possible to replace the transport layer
without rewriting the encryption or TUN logic.

For example, the planned UDP transition should primarily replace the
transport semantics while preserving the higher-level relationship:

``` text
TUN ↔ Tunnel ↔ Transport
```

------------------------------------------------------------------------

# 30. Safety Notice

TunnelForge is intended for controlled educational and research
environments.

Do not use it as a replacement for mature VPN software or assume that
the current protocol provides the security properties of production VPN
protocols such as WireGuard.

Use isolated machines, virtual machines, network namespaces, or a
private lab network when experimenting with routing and packet
forwarding.

------------------------------------------------------------------------

# 31. License

Choose and add a license appropriate for your project.

For example:

``` text
MIT License
```

If using the MIT License, add a `LICENSE` file containing the official
license text.

------------------------------------------------------------------------

# 32. Quick Start

For a quick test on two Linux endpoints:

### Server

``` bash
git clone <YOUR-GITHUB-REPOSITORY-URL>
cd TunnelForge

python3 -m venv .venv
source .venv/bin/activate
pip install cryptography

sudo python3 server.py
```

### Client

``` bash
git clone <YOUR-GITHUB-REPOSITORY-URL>
cd TunnelForge

python3 -m venv .venv
source .venv/bin/activate
pip install cryptography

sudo python3 client.py
```

Before launching the two processes, make sure:

1.  The server identity keys exist.
2.  The client identity keys exist.
3.  `trusted_server_public.bin` contains the server public identity key.
4.  `trusted_client_public.bin` contains the client public identity key.
5.  The client's `HOST` points to the server.
6.  TCP port `5555` is reachable.
7.  `/dev/net/tun` is available.
8.  Required routes have been configured for the test topology.

------------------------------------------------------------------------

## 33. Project Goal

The goal of TunnelForge is not merely to create a working encrypted
socket.

It is to understand the individual building blocks of a VPN:

``` text
Linux TUN
   ↓
IP packet handling
   ↓
Packet encryption
   ↓
Key exchange
   ↓
Peer authentication
   ↓
Secure transport
   ↓
Routing
   ↓
Real application traffic
```

By implementing these components separately, TunnelForge provides a
practical environment for studying:

-   Linux networking
-   Virtual network interfaces
-   Socket programming
-   VPN architecture
-   Public-key cryptography
-   Authenticated key exchange
-   AEAD encryption
-   Routing
-   Network namespaces
-   Packet inspection
-   Protocol design
-   Security engineering
