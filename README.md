# TunnelForge

TunnelForge is a Python-based encrypted TCP communication project.

It demonstrates how two devices can establish a secure communication channel using:

* TCP sockets
* Elliptic Curve Diffie-Hellman (ECDH)
* P-256 elliptic curve cryptography
* HKDF-SHA256
* AES-256-GCM authenticated encryption
* Random nonces
* Length-prefixed TCP message framing
* Graceful connection handling
* Windows ↔ Android/Termux communication

The project was built step-by-step to understand how encrypted network communication works rather than relying on a high-level VPN library.

> **Current status:** TunnelForge is an encrypted TCP communication prototype. It is not yet a complete production VPN.

---

## 1. How TunnelForge Works

The basic communication flow is:

```text
                TunnelForge
                     |
        +------------+------------+
        |                         |
     Client                    Server
        |                         |
        | ---- TCP Connect ------>|
        |                         |
        | <--- ECDH Public Key -->|
        |                         |
        | ---- ECDH Public Key -->|
        |                         |
        |    Shared Secret        |
        |       derived           |
        |                         |
        |       HKDF              |
        |         ↓               |
        |   32-byte AES key       |
        |                         |
        |==== AES-GCM Messages ===>|
        |                         |
        |<=== AES-GCM Reply ======|
```

The important point is that the client and server do **not** directly send the AES encryption key to each other.

Instead, both sides independently derive the same shared secret using ECDH.

---

# 2. Project Structure

The current project contains:

```text
TunnelForge/
│
├── .gitignore
├── client.py
├── server.py
└── README.md
```

### `server.py`

The server:

1. Creates a TCP socket.
2. Listens for incoming connections.
3. Performs the ECDH key exchange.
4. Derives the encryption key using HKDF.
5. Receives encrypted messages.
6. Decrypts messages using AES-GCM.
7. Detects the `exit` message.
8. Sends an encrypted acknowledgement.
9. Closes the connection gracefully.

### `client.py`

The client:

1. Creates a TCP socket.
2. Connects to the server.
3. Performs the ECDH key exchange.
4. Derives the same encryption key.
5. Encrypts messages using AES-GCM.
6. Sends encrypted messages to the server.
7. Sends `exit` when finished.
8. Receives and decrypts the server acknowledgement.
9. Closes the connection gracefully.

---

# 3. Requirements

## Server/Client computer

Python 3 is required.

Check your Python installation:

```powershell
python --version
```

You also need the Python `cryptography` package.

Install it with:

```powershell
pip install cryptography
```

If `pip` is associated with another Python installation, use:

```powershell
python -m pip install cryptography
```

---

# 4. Run TunnelForge on One Computer

This is the easiest way to test the project.

Both the server and client can run on the same computer using:

```text
127.0.0.1
```

This is called the **localhost** address.

The server uses port:

```text
5555
```

---

## Step 1 — Start the server

Open a terminal in the TunnelForge directory.

Run:

```powershell
python server.py
```

The server should display something similar to:

```text
Server listening on 0.0.0.0:5555
```

The server is now waiting for a client.

---

## Step 2 — Start the client

Open a second terminal in the same directory.

Run:

```powershell
python client.py
```

Make sure the client is configured to connect to:

```text
127.0.0.1
```

The client should establish a connection with the server.

---

## Step 3 — Send messages

The client will ask:

```text
Enter the message:
```

For example:

```text
Enter the message: Hello
Enter the message: This is TunnelForge
Enter the message: Testing encrypted communication
```

The server receives and decrypts the messages.

You should see something similar to:

```text
Client says: Hello
Client says: This is TunnelForge
Client says: Testing encrypted communication
```

---

## Step 4 — End the connection

Enter:

```text
exit
```

The client sends the encrypted `exit` message.

The server detects it and sends an encrypted acknowledgement.

The client then displays:

```text
Server replied : Message received!!!
```

The connection is closed gracefully.

---

# 5. Understanding the Encryption

TunnelForge uses several cryptographic components.

## ECDH

TunnelForge uses:

```text
Elliptic Curve Diffie-Hellman
```

with:

```text
SECP256R1 / P-256
```

Both client and server generate temporary key pairs.

Each side has:

```text
Private Key
Public Key
```

The public keys are exchanged.

The private key remains on the device.

Both sides then calculate the same shared secret.

Conceptually:

```text
Client Private Key + Server Public Key
                    ↓
              Shared Secret

Server Private Key + Client Public Key
                    ↓
              Shared Secret
```

Both calculations produce the same secret.

---

# 6. HKDF

The raw ECDH shared secret is not directly used as the AES key.

TunnelForge derives a 32-byte encryption key using:

```text
HKDF
```

with:

```text
SHA-256
```

The current derivation uses:

```text
info = b"VPN Key"
```

The resulting key is:

```text
32 bytes = 256 bits
```

This becomes the AES-GCM key.

---

# 7. AES-GCM

TunnelForge uses:

```text
AES-256-GCM
```

AES-GCM provides both:

* Confidentiality
* Integrity/authentication

Therefore, the receiver can detect if encrypted data has been modified.

The message is structured approximately as:

```text
[4-byte length]
        |
        +-- [12-byte nonce]
        |
        +-- [ciphertext + authentication tag]
```

---

# 8. Nonces

Each AES-GCM message receives a new random 12-byte nonce.

TunnelForge generates it using:

```python
os.urandom(12)
```

`os.urandom()` uses the operating system's cryptographically secure random source.

The nonce does not need to be secret.

The important requirement with AES-GCM is that a nonce must not be reused with the same encryption key.

---

# 9. TCP Message Framing

TCP is a byte stream.

It does not preserve individual application messages.

For example, if the client sends:

```text
Hello
World
```

TCP does not guarantee that the server receives exactly:

```text
Hello
World
```

as two separate `recv()` calls.

TunnelForge therefore uses length-prefix framing.

Each message begins with:

```text
4-byte message length
```

followed by the encrypted data.

The format is:

```text
[4-byte length][encrypted message]
```

The project also uses:

```python
recv_exactly()
```

to ensure that the requested number of bytes is actually received before processing the message.

---

# 10. Testing on Two Devices

TunnelForge can also communicate between two devices on the same local network.

For example:

```text
Windows Laptop
      |
      | Wi-Fi / Phone Hotspot
      |
Android Phone
```

The laptop runs:

```text
server.py
```

The phone runs:

```text
client.py
```

---

# 11. Find the Laptop IP Address

On Windows, open PowerShell and run:

```powershell
ipconfig
```

Look for the network adapter that is currently being used.

For example:

```text
IPv4 Address. . . . . . . . . . . : 10.160.1.155
```

The actual address will depend on your network.

Do not copy the example address above unless it is actually shown by your `ipconfig`.

---

# 12. Configure the Client

In `client.py`, the client should connect to the laptop's current LAN/hotspot IP.

For example:

```text
192.xx.xx
```

The port remains:

```text
5555
```

The important difference is:

### Localhost testing

```text
127.0.0.1:5555
```

### Another device

```text
<Device-IP>:5555
```

For example:

```text
192.xx.xx:5555
```

---

# 13. Windows Firewall

When the server is first run, Windows may show a firewall notification asking whether Python should be allowed through the firewall.

For testing on your private network, allow Python on the appropriate **Private network** profile.

If Windows Firewall blocks port `5555`, the phone may be unable to connect even when the IP address is correct.

---

# 14. Android / Termux Setup

TunnelForge can also run its Python client on an Android phone using **Termux**.

Install Termux from a trusted source such as the official Termux project/F-Droid distribution.

Open Termux and update its package information:

```bash
pkg update
```

Then install Python:

```bash
pkg install python
```

---

# 15. Install Cryptography on Termux

The standard:

```bash
pip install cryptography
```

may attempt to build dependencies and fail on Android.

Termux provides a prebuilt package, so install:

```bash
pkg install python-cryptography
```

Then verify:

```bash
python -c "import cryptography; print(cryptography.__version__)"
```

You should see the installed version.

---

# 16. Copy `client.py` to the Android Phone

The easiest approach is to place `client.py` in the Android Download directory.

In Termux, allow storage access:

```bash
termux-setup-storage
```

After granting permission, Termux provides access through:

```text
~/storage/downloads/
```

For example:

```bash
ls ~/storage/downloads/
```

If `client.py` is there, copy it to the Termux home directory:

```bash
cp ~/storage/downloads/client.py ~/
```

Now verify:

```bash
ls ~/
```

You should see:

```text
client.py
```

---

# 17. Test Network Connectivity

Before running the Python client, you can test whether the phone can reach the laptop's TCP port.

Install netcat if necessary:

```bash
pkg install netcat-openbsd
```

Then run:

```bash
nc <LAPTOP-IP> 5555
```

For example:

```bash
nc 10.160.1.155 5555
```

If the server reports a connection, basic network connectivity is working.

The `nc` test itself does not perform TunnelForge's cryptographic handshake, so the server may subsequently report a connection error. That is expected.

`nc` is only being used here to test the TCP connection.

---

# 18. Run the TunnelForge Client on Android

Once network connectivity is confirmed:

```bash
python ~/client.py
```

The Android phone becomes the TunnelForge client.

The Windows laptop runs:

```bash
python server.py
```

The communication path is:

```text
Android / Termux
       |
       | TCP :5555
       |
       ↓
Windows Laptop
       |
       ↓
TunnelForge Server
```

Messages are encrypted before being sent over the TCP connection.

---

# 19. Example Phone-to-Laptop Test

### Laptop

Run:

```powershell
python server.py
```

### Android

Run:

```bash
python ~/client.py
```

Then enter:

```text
Hello from Android
```

The server should decrypt and display:

```text
Client says: Hello from Android
```

You can send multiple messages:

```text
Hello from Android
This is TunnelForge
Testing encrypted communication
```

Finally:

```text
exit
```

The server sends the encrypted acknowledgement.

---

# 20. Connection Handling

TunnelForge includes basic graceful connection handling.

The program handles situations such as:

* Unexpected TCP connection closure
* User pressing `Ctrl+C`
* Normal `exit` command
* Closing client sockets
* Closing server sockets

The code uses `try`, `except`, and `finally` blocks so sockets are closed even when the program is interrupted.

---

# 21. Security Demonstration

AES-GCM provides authentication in addition to encryption.

If encrypted data is modified, the authentication tag becomes invalid.

TunnelForge was tested by deliberately modifying encrypted data.

Conceptually:

```text
Original encrypted message
          ↓
       Modified
          ↓
     AES-GCM decrypt
          ↓
      InvalidTag
```

The modified message is therefore rejected instead of being silently accepted as valid plaintext.

---

# 22. Current Protocol

The current TunnelForge protocol can be summarized as:

```text
1. TCP connection
       ↓
2. Client generates ephemeral ECDH key pair
       ↓
3. Server generates ephemeral ECDH key pair
       ↓
4. Exchange public keys
       ↓
5. Calculate ECDH shared secret
       ↓
6. HKDF-SHA256
       ↓
7. Derive 32-byte AES key
       ↓
8. Encrypt messages using AES-GCM
       ↓
9. Add length prefix
       ↓
10. Send through TCP
       ↓
11. Receiver reads exact length
       ↓
12. AES-GCM authentication + decryption
       ↓
13. Process plaintext
```

---

# 23. Example Wire Format

A normal encrypted message is transmitted as:

```text
+----------------------+-----------------------------+
| 4-byte length        | Encrypted message           |
+----------------------+-----------------------------+
                           |
                           +-- 12-byte nonce
                           |
                           +-- ciphertext
                           |
                           +-- GCM authentication tag
```

The length field allows the receiver to determine exactly how many bytes belong to the encrypted message.

---

# 24. Important Security Notes

TunnelForge is currently an educational security/networking project.

It demonstrates important cryptographic concepts, but it should not yet be considered a production VPN or secure messaging application.

For example, the current protocol does not yet provide:

* Peer identity authentication
* Certificate infrastructure
* Protection against active man-in-the-middle attacks
* Separate encryption keys for each communication direction
* Persistent identity keys
* Replay protection beyond the properties provided by the current session design
* Production-grade session management
* Automatic key rotation
* Full VPN packet tunneling
* Operating-system-level routing

ECDH establishes a shared secret, but by itself it does not prove who the other endpoint is.

---