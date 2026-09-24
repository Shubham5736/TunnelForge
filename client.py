import socket
import os

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# Generate emphemeral ECDH key pair
private_key = ec.generate_private_key(ec.SECP256R1())
publlic_key = private_key.public_key()
public_key_bytes = publlic_key.public_bytes(encoding=serialization.Encoding.X962, format=serialization.PublicFormat.CompressedPoint)

HOST ="192.168.1.4"
PORT = 5555

def recv_exactly(sock, number_of_bytes):
    data = b""
    while len(data) <number_of_bytes:
        chunk=sock.recv(number_of_bytes - len(data))
        if not chunk:
            raise ConnectionError("Connection closed before receiving all data")
        data += chunk
    return data


#Create TCP socket, connect to server
client_socket=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
client_socket.connect((HOST, PORT))
#Send client's public key and receive server's public key
client_socket.sendall(public_key_bytes)
print("Client public key sent")
server_public_key_bytes =recv_exactly(client_socket, 33)
print("Recieved server public key:")
server_public_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), server_public_key_bytes)
print("Server public key reconstructed successfully")

#calculate the shared secret
shared_secret = private_key.exchange(ec.ECDH(),server_public_key)
encryption_key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"VPN Key").derive(shared_secret)
aesgcm = AESGCM(encryption_key)
print("AES-GCM initialized on client")


#Get message from user, and send it to server
try:
    while True:
        message = input("Enter the message: ")
        plaintext = message.encode("utf-8")
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce,plaintext,None)
        encrypted_message = nonce + ciphertext
        message_length = len(encrypted_message)
        length_bytes = message_length.to_bytes(4, byteorder="big")
        client_socket.sendall(length_bytes + encrypted_message)
        if message.lower() == "exit":
            break

    #Acoknowledgement from server
    length_data = recv_exactly(client_socket,4)
    reply_length = int.from_bytes(length_data, byteorder="big")
    encrypted_reply = recv_exactly(client_socket,reply_length)
    reply_nonce = encrypted_reply[:12]
    reply_ciphertext = encrypted_reply[12:]
    reply_plaintext = aesgcm.decrypt(reply_nonce,reply_ciphertext,None)
    reply = reply_plaintext.decode("utf-8")
    print(f"Server replied : {reply}")
    
except ConnectionError:
    print("Connection closed unexpectedly")
except KeyboardInterrupt:
    print("\nConnection interrupted by user!!!")
finally:
    client_socket.close()