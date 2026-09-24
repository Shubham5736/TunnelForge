import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric.x25519 import (X25519PrivateKey,X25519PublicKey)
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import (Encoding, PublicFormat)

class Encryption:
    KEY_SIZE = 32
    NONCE_SIZE = 12
    def __init__(self, key):
        if len(key) not in (16, 24, 32):
            raise ValueError("AES key must be 16, 24, or 32 bytes")

        self.key = key
        self.aesgcm = AESGCM(key)

    @staticmethod
    def generate_key():
        return AESGCM.generate_key(bit_length=256)

    @staticmethod
    def generate_key_exchange():
        return X25519PrivateKey.generate()

    @staticmethod
    def get_public_key(private_key):
        return private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)

    @staticmethod
    def derive_session_key(private_key, peer_public_key):
        peer_key = X25519PublicKey.from_public_bytes(peer_public_key)

        shared_secret = private_key.exchange(peer_key)
        session_key = HKDF(
            algorithm=hashes.SHA256(), 
            length=32, 
            salt=None, 
            info=b"TunnelForge-v1"
        ).derive(shared_secret)

        return session_key

    def encrypt(self, plaintext):
        nonce = os.urandom(self.NONCE_SIZE)
        ciphertext = self.aesgcm.encrypt(nonce,plaintext,None)

        return nonce + ciphertext

    def decrypt(self, encrypted_data):
        if len(encrypted_data)< self.NONCE_SIZE:
            raise ValueError("Encryption data is too short")

        nonce = encrypted_data[:self.NONCE_SIZE]
        ciphertext = encrypted_data[self.NONCE_SIZE:]

        plaintext = self.aesgcm.decrypt(nonce,ciphertext,None)
        return plaintext


# --------------------------------------------------
# Temporary standalone test
# Remove this section during integration
# --------------------------------------------------

if __name__ == "__main__":

    print("Testing TunnelForge in-memory key management...")

    print("\nGenerating X25519 keys...")

    client_private = Encryption.generate_key_exchange()
    server_private = Encryption.generate_key_exchange()

    client_public = Encryption.get_public_key(client_private)
    server_public = Encryption.get_public_key(server_private)

    print(f"Client public key length: {len(client_public)} bytes")
    print(f"Server public key length: {len(server_public)} bytes")

    print("\nDeriving session keys...")

    client_session_key = Encryption.derive_session_key(
        client_private,
        server_public
    )

    server_session_key = Encryption.derive_session_key(
        server_private,
        client_public
    )

    print(f"Client session key length: {len(client_session_key)} bytes")
    print(f"Server session key length: {len(server_session_key)} bytes")

    if client_session_key == server_session_key:
        print("\nSession key exchange successful")
    else:
        print("\nSession key exchange failed")
        raise RuntimeError("Session keys do not match")

    print("\nTesting AES-GCM with derived session key...")

    client_crypto = Encryption(client_session_key)
    server_crypto = Encryption(server_session_key)

    original_data = b"TunnelForge secure in-memory session test"

    encrypted_data = client_crypto.encrypt(original_data)
    decrypted_data = server_crypto.decrypt(encrypted_data)

    print(f"Original data: {original_data}")
    print(f"Encrypted data length: {len(encrypted_data)} bytes")
    print(f"Decrypted data: {decrypted_data}")

    if decrypted_data == original_data:
        print("\nEncryption test successful")
    else:
        print("\nEncryption test failed")