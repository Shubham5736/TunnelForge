import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric.x25519 import (X25519PrivateKey,X25519PublicKey)
from cryptography.hazmat.primitives.asymmetric.ed25519 import (Ed25519PrivateKey, Ed25519PublicKey)
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
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

    @staticmethod
    def generate_identity_key():
        return Ed25519PrivateKey.generate()

    @staticmethod
    def save_identity_key(private_key, private_path, public_path):
        private_path = Path(private_path)
        public_path = Path(public_path)

        

        private_path.parent.mkdir(parents=True, exist_ok=True)
        public_path.parent.mkdir(parents=True, exist_ok=True)

        private_data = private_key.private_bytes_raw()

        public_data = private_key.public_key().public_bytes_raw()

        private_path.write_bytes(private_data)
        public_path.write_bytes(public_data)

        #Private key must be accessible by the owner
        os.chmod(private_path, 0o600)
        os.chmod(public_path, 0o644)

    @staticmethod
    def load_identity_key(private_path):
        private_path = Path(private_path)

        private_data = private_path.read_bytes()

        if len(private_data) != 32:
            raise ValueError("Invalid Ed25519 Private key: expected 32 bytes")
        
        return Ed25519PrivateKey.from_private_bytes(private_data)

    @staticmethod
    def sign(private_key, data):
        return private_key.sign(data)

    @staticmethod
    def verify(public_key, signature, data):
        try:
            public_key.verify(signature,data)
            return True
        except:
            return False

    @staticmethod
    def create_signed_ephemeral_key(identity_private_key, ephemeral_public_key):
        if len(ephemeral_public_key) != 32:
            raise ValueError("Invalid X25519 public key: expected 32 bytes")

        signature = Encryption.sign(identity_private_key, ephemeral_public_key)

        return ephemeral_public_key + signature

    @staticmethod
    def parse_signed_empheral_key(payload):
        if len(payload) != 96:
            raise ValueError("Invalid signed empheral key payload: expected 95 bytes")

        ephemeral_public_key = payload[:32]
        signature = payload[32:]

        return ephemeral_public_key, signature
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


    # ---------------------------------------------------------
    # Persistent Ed25519 identity keys
    # ---------------------------------------------------------

    client_private_path = "keys/client/identity_private.bin"
    client_public_path = "keys/client/identity_public.bin"

    server_private_path = "keys/server/identity_private.bin"
    server_public_path = "keys/server/identity_public.bin"

    print("\nTesting persistent identity keys...")

    # Generate and save identity keys only if they do not exist
    if not (
        Path(client_private_path).exists()
        and Path(client_public_path).exists()
    ):
        client_identity = Encryption.generate_identity_key()

        Encryption.save_identity_key(
            client_identity,
            client_private_path,
            client_public_path
        )

        print("Client identity generated and saved")
    else:
        print("Client identity already exists")


    if not (
        Path(server_private_path).exists()
        and Path(server_public_path).exists()
    ):
        server_identity = Encryption.generate_identity_key()

        Encryption.save_identity_key(
            server_identity,
            server_private_path,
            server_public_path
        )

        print("Server identity generated and saved")
    else:
        print("Server identity already exists")


    print("\nClient identity:")
    print(f"  Private: {client_private_path}")
    print(f"  Public : {client_public_path}")

    print("\nServer identity:")
    print(f"  Private: {server_private_path}")
    print(f"  Public : {server_public_path}")


    # ---------------------------------------------------------
    # Loading identity keys from storage
    # ---------------------------------------------------------

    print("\nTesting persistent identity loading...")

    loaded_client_identity = Encryption.load_identity_key(
        client_private_path
    )

    loaded_server_identity = Encryption.load_identity_key(
        server_private_path
    )

    print("Client identity loaded successfully")
    print("Server identity loaded successfully")


    # Get public keys from the loaded private keys
    loaded_client_public = loaded_client_identity.public_key()
    loaded_server_public = loaded_server_identity.public_key()


    # Serialize public keys for comparison
    original_client_public = Path(
        client_public_path
    ).read_bytes()

    loaded_client_public_bytes = loaded_client_public.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )


    original_server_public = Path(
        server_public_path
    ).read_bytes()

    loaded_server_public_bytes = loaded_server_public.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )


    # Verify client identity
    if original_client_public == loaded_client_public_bytes:
        print("Client identity continuity verified")
    else:
        raise RuntimeError("Client identity changed after loading")


    # Verify server identity
    if original_server_public == loaded_server_public_bytes:
        print("Server identity continuity verified")
    else:
        raise RuntimeError("Server identity changed after loading")


    print("Step 3.2.6 test PASSED")


    # ---------------------------------------------------------
    # Trusted peer identity keys
    # ---------------------------------------------------------

    print("\nTesting trusted peer identity keys...")

    trusted_server_public = Path(
        "keys/client/trusted_server_public.bin"
    ).read_bytes()

    server_public = Path(
        "keys/server/identity_public.bin"
    ).read_bytes()

    trusted_client_public = Path(
        "keys/server/trusted_client_public.bin"
    ).read_bytes()

    client_public = Path(
        "keys/client/identity_public.bin"
    ).read_bytes()


    # Verify client trusts the correct server identity
    if trusted_server_public == server_public:
        print("Client trusts the correct server identity")
    else:
        raise RuntimeError(
            "Client trusted server key does not match server identity"
        )


    # Verify server trusts the correct client identity
    if trusted_client_public == client_public:
        print("Server trusts the correct client identity")
    else:
        raise RuntimeError(
            "Server trusted client key does not match client identity"
        )


    # Verify trusted public key lengths
    if len(trusted_server_public) != 32:
        raise RuntimeError(
            "Invalid trusted server public key length"
        )

    if len(trusted_client_public) != 32:
        raise RuntimeError(
            "Invalid trusted client public key length"
        )


    print("Trusted identity verification successful")
    print("Step 3.2.7 test PASSED")

    # ---------------------------------------------------------
    # Ed25519 signing and verification
    # ---------------------------------------------------------

    print("\nTesting Ed25519 signing and verification...")

    test_message = b"TunnelForge ephemeral X25519 public key"

    #sign using the client's persistent identity
    client_signature = Encryption.sign(loaded_client_identity, test_message)

    print(f"Signature length: {len(client_signature)} bytes")
    if len(client_signature) != 64:
        raise RuntimeError("Invalid Ed25519 signature length")

    #verify using the cleints public identity
    client_identity_public = loaded_client_identity.public_key()
    
    if Encryption.verify(client_identity_public, client_signature, test_message):
        print("Valid Signature verifies successfully")
    
    else:
        raise RuntimeError("Valid signature verification failed")

    # Test that modified data is rejected
    modified_message = b"Modified X25519 public key"

    if Encryption.verify(client_identity_public, client_signature, modified_message):
        raise RuntimeError("Modified message was incorrectly accepted")
    else:
        print("Modified message correctly rejected")

    print("Step 3.3.1 test PASSED")

    # ---------------------------------------------------------
    # Signed ephemeral X25519 handshake payload
    # ---------------------------------------------------------
    print("\nTesting X25519 handshake payload")

    test_ephemeral_private = Encryption.generate_key_exchange()
    test_ephemeral_public = Encryption.get_public_key(test_ephemeral_private)
    signed_payload = Encryption.create_signed_ephemeral_key(loaded_client_identity, test_ephemeral_public)
    print(f"Ephemeral public key length: {len(test_ephemeral_public)} bytes")
    print(f"Signed payload length: {len(signed_payload)} bytes")
    
    if len(signed_payload) != 96:
        raise RuntimeError("Invalid signed ephemeral key payload length")

    parsed_ephemeral_public, parsed_signature = (Encryption.parse_signed_empheral_key(signed_payload))

    if parsed_ephemeral_public != test_ephemeral_public:
        raise RuntimeError("Parsed ephemeral public key does not match original")

    if len(parsed_signature) != 64:
        raise RuntimeError("Invalid parsed Ed25519 signature length")

    print("\nVerifying signed ephemeral key...")

    # First verify using the public key derived directly
    # from the same persistent client identity
    direct_client_public = loaded_client_identity.public_key()

    if Encryption.verify(
        direct_client_public,
        parsed_signature,
        parsed_ephemeral_public
    ):
        print("Direct identity verification successful")
    else:
        raise RuntimeError(
            "Direct identity verification failed"
        )

    # Now verify using the trusted client public key
    trusted_client_public_bytes = Path(
        "keys/server/trusted_client_public.bin"
    ).read_bytes()

    if len(trusted_client_public_bytes) != 32:
        raise RuntimeError(
            "Trusted client public key must be exactly 32 bytes"
        )

    trusted_client_public = Ed25519PublicKey.from_public_bytes(
        trusted_client_public_bytes
    )

    if Encryption.verify(
        trusted_client_public,
        parsed_signature,
        parsed_ephemeral_public
    ):
        print("Trusted identity verification successful")
    else:
        raise RuntimeError(
            "Trusted identity verification failed"
        )

    print("Step 3.3.2 test PASSED")

    print("\nTesting tampered ephemeral key rejection...")

    # Simulate a MITM modifying the ephemeral X25519 public key
    tampered_ephemeral_public = bytearray(parsed_ephemeral_public)
    tampered_ephemeral_public[0] ^= 0x01
    tampered_ephemeral_public = bytes(tampered_ephemeral_public)

    print("Original ephemeral key verification: True")

    # The signature belongs to the ORIGINAL ephemeral public key.
    # Verification must therefore fail for the modified key.
    tampered_valid = Encryption.verify(
        trusted_client_public,
        parsed_signature,
        tampered_ephemeral_public
    )

    print(f"Tampered ephemeral key verification: {tampered_valid}")

    if tampered_valid:
        raise RuntimeError(
            "SECURITY FAILURE: tampered ephemeral key was accepted"
        )

    print("MITM tampering correctly rejected")
    print("Step 3.5 test PASSED")