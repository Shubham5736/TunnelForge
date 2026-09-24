import os
import fcntl
import struct


class TunDevice:
    TUNSETIFF = 0x400454ca
    IFF_TUN = 0x0001
    IFF_NO_PI = 0x1000

    def __init__(self, name="tun0"):
        self.name = name
        self.fd = None

    def create(self):
        self.fd = os.open("/dev/net/tun", os.O_RDWR)

        ifr = struct.pack(
            "16sH22x",
            self.name.encode("utf-8"),
            self.IFF_TUN | self.IFF_NO_PI
        )

        fcntl.ioctl(self.fd, self.TUNSETIFF, ifr)

        print(f"TUN interface '{self.name}' created")

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def read_packet(self):
        if self.fd is None:
            raise RuntimeError("TUN interface is not open")
        packet = os.read(self.fd,65535)
        return packet

    def write_packet(self,packet):
        if self.fd is None:
            raise RuntimeError("TUN interface is not open")
        os.write(self.fd,packet)
        
# --------------------------------------------------
# Temporary standalone test
# Remove this section during integration
# --------------------------------------------------

if __name__ == "__main__":
    tun = TunDevice("tun0")

    try:
        tun.create()

        print("TUN interface created")
        print("Waiting for a packet...")

        packet = tun.read_packet()

        print(f"Packet received: {len(packet)} bytes")

        tun.write_packet(packet)

        print("Packet written back to TUN")
        input("Press Enter to close TUN...")

    except KeyboardInterrupt:
        print("\nTest interrupted")

    finally:
        tun.close()
        print("TUN interface closed")