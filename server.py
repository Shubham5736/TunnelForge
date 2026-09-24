import socket
import os

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

HOST ="127.0.0.1"
PORT = 5555

def recv_exactly(sock, number_of_bytes):
    data = b""
    while len(data) <number_of_bytes:
        chunk=sock.recv(number_of_bytes - len(data))
        if not chunk:
            raise ConnectionError("Connection closed before receiving all data")
        data += chunk
    return data

# Generate emphemeral ECDH key pair
private_key = ec.generate_private_key(ec.SECP256R1())
publlic_key = private_key.public_key()
public_key_bytes = publlic_key.public_bytes(encoding=serialization.Encoding.X962, format=serialization.PublicFormat.CompressedPoint)

#This is the socket connection to extablish a link to the client
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((HOST, PORT))
server_socket.listen(1)
print(f"Server listening on {HOST}:{PORT}")
client_socket,client_address = server_socket.accept()
print(f"Connected by {client_address}")
#Receive client's public key
client_public_ley_bytes = recv_exactly(client_socket,33)
client_public_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), client_public_ley_bytes)
print("Client public key reconstructed successfully")

#calculate shared secret
shared_secret = private_key.exchange(ec.ECDH(), client_public_key)
encryption_key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"VPN Key").derive(shared_secret)
aesgcm = AESGCM(encryption_key)
print("AES-GCM initilized on server")


#Send server's Public key
client_socket.sendall(public_key_bytes)
print("server public key sent")

#The server is listening and waiting for a message from the client
try:
    while True:
        length_data = recv_exactly(client_socket, 4)
        message_length =int.from_bytes(length_data, byteorder="big")
        encrypted_message = recv_exactly(client_socket,message_length)
        nonce = encrypted_message[:12]
        ciphertext = encrypted_message[12:]
        plaintext = aesgcm.decrypt(nonce,ciphertext,None)
        message = plaintext.decode("utf-8")
        if message.lower() == "exit":
            break
        print(f"Client says: {message}")

    #The server is sending back the reply
    reply = "Message received!!!"
    reply_plaintext = reply.encode("utf-8")
    reply_nonce = os.urandom(12)
    reply_ciphertext = aesgcm.encrypt(reply_nonce,reply_plaintext,None)
    encrypted_reply = reply_nonce + reply_ciphertext
    reply_length = len(encrypted_reply)
    reply_length_bytes = reply_length.to_bytes(4, byteorder="big")
    client_socket.sendall(reply_length_bytes + encrypted_reply)

except ConnectionError:
    print("Connection closed unexpectedly!!!")
except KeyboardInterrupt:
    print("\nServer interrupted by user!!!")
finally:
    client_socket.close()
    server_socket.close()