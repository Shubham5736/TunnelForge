import threading

class Tunnel:

    def __init__(self, tun, transport, crypto):
        self.tun = tun
        self.transport = transport
        self.crypto = crypto
        self.running = True

    def tun_to_network(self):
        while self.running:
            packet = self.tun.read_packet()
            encrypted_packet = self.crypto.encrypt(packet)
            self.transport.send(encrypted_packet)

    def network_to_tun(self):
        while self.running:
            encrypted_packet = self.transport.receive()
            packet = self.crypto.decrypt(encrypted_packet)
            self.tun.write_packet(packet)
            

    def start(self):
        tun_thread = threading.Thread(target=self.tun_to_network)
        network_thread = threading.Thread(target=self.network_to_tun)
        
        tun_thread.start()
        network_thread.start()

        tun_thread.join()
        network_thread.join()

    def stop(self):
        self.running = False

if __name__ == "__main__":
    print("Tunnel module loaded successfully")
