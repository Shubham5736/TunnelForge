import socket

class Transport:
    def __init__(self,sock=None):
        self.sock = sock
    
    def connect(self,host,port):
        self.sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.sock.connect((host, port))
        print(f"Connected to {host}:{port}")

    def send(self,data):
        if self.sock is None:
            raise RuntimeError("Transport is not connected")
        length = len(data)
        length_bytes = length.to_bytes(4, byteorder="big")
        self.sock.sendall(length_bytes + data)

    def receive_exactly(self, number_of_bytes):
        if self.sock is None:
            raise RuntimeError("Transport is not connected")
        data = b""

        while len(data) < number_of_bytes:
            chunk = self.sock.recv(number_of_bytes - len(data))
            if not chunk:
                raise ConnectionError("Connection closed before receiving all data")
            data += chunk
        return data
    
    def receive(self):
        length_bytes = self.receive_exactly(4)
        length = int.from_bytes(length_bytes, byteorder="big")
        return self.receive_exactly(length)

    def close(self):
        if self.sock is not None:
            self.sock.close()
            self.sock = None

# --------------------------------------------------
# Temporary standalone test
# Remove this section during integration
# --------------------------------------------------

if __name__ == "__main__":
    transport = Transport()
    
    try:
        transport.connect("127.0.0.1",5555)
        test_data = b"TunnerForge transport test"
        transport.send(test_data)
        print("Framed test data sent successfully")
    
    except ConnectionRefusedError:
        print("Counld not connect to server")
    
    except KeyboardInterrupt:
        print("\nTest interrupted")

    finally:
        transport.close()
        print("\nTransport closed!!!")