""" Implementation of a SlippiComm client aka 'Slippstream'
                                                    (I'm calling it that)

This can be used to talk to some server implementing the SlippiComm protocol
(i.e. the Project Slippi fork of Nintendont).
"""

import errno
import select
import signal
import socket
from enum import Enum
from struct import pack, unpack
from sys import argv

import ubjson
from hexdump import hexdump
from ubjson.decoder import DecoderException


class EventType(Enum):
    """Replay event types"""

    GECKO_CODES = 0x10
    PAYLOADS = 0x35
    GAME_START = 0x36
    PRE_FRAME = 0x37
    POST_FRAME = 0x38
    GAME_END = 0x39
    FRAME_START = 0x3A
    ITEM_UPDATE = 0x3B
    FRAME_BOOKEND = 0x3C


class CommType(Enum):
    """Types of SlippiComm messages"""

    HANDSHAKE = 0x01
    REPLAY = 0x02
    KEEPALIVE = 0x03


# The null token used for initial SlippiComm handshakes
NULL_TOKEN = b"\x00\x00\x00\x00"


class SlippstreamClient(object):
    """Container representing a client to some SlippiComm server"""

    def __init__(self, address="", port=51441, realtime=True):
        """Constructor for this object"""

        self.remote_addr = None
        self.remote_port = None
        self.buf = bytearray()
        self.frame_num = None
        self.server = None
        self.out = None
        self.inp = None
        self.realtime = realtime
        self.address = address
        self.port = port

    def shutdown(self):
        if self.server != None:
            self.server.close()
            return True
        else:
            return None

    def read_message(self):
        """Read an entire message from the registered socket.

        Returns None on failure, Dict of data from ubjson on success.
        """
        while True:
            try:
                rd, wr, exc = select.select(self.inp, self.out, self.inp)
                if len(rd) < 1:
                    continue
            except OSError as e:
                if e.args[0] == errno.EBADF:
                    print("Socket closed, shutting down")
                    return None
            for s in rd:
                try:
                    # The first 4 bytes are the message's length
                    #   read this first
                    while len(self.buf) < 4:
                        self.buf += s.recv(4 - len(self.buf))
                    message_len = unpack(">L", self.buf[0:4])[0]

                    # Now read in message_len amount of data
                    while len(self.buf) < (message_len + 4):
                        self.buf += s.recv((message_len + 4) - len(self.buf))

                    try:
                        # Exclude the the message length in the header
                        msg = ubjson.loadb(self.buf[4:])
                        # Clear out the old buffer
                        del self.buf
                        self.buf = bytearray()
                        return msg

                    except DecoderException as e:
                        print("ERROR: Decode failure in Slippstream")
                        print(e)
                        print(hexdump(self.buf[4:]))
                        self.buf.clear()
                        return None

                except socket.error as e:
                    if e.args[0] == errno.EWOULDBLOCK:
                        continue
                    else:
                        print("ERROR with socket:", e)
                        return None

    def connect(self):
        """Connect to the server

        Returns True on success, False on failure
        """

        # If we don't have a slippi address, let's autodiscover it
        if not self.address:
            # Slippi broadcasts a UDP message on port
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Slippi sends an advertisement every 10 seconds. So 20 should be enough
            sock.settimeout(20)
            sock.bind(("", 20582))
            try:
                print("Trying to autodiscover Slippi...")
                message = sock.recvfrom(1024)
                self.address = message[1][0]
                print("Found Slippi at IP address: ", self.address)
            except socket.timeout:
                print(
                    "ERROR: Could not autodiscover a slippi console, and "
                    + "no address was given. Make sure the Wii/Slippi console is on "
                    + "and/or supply a known IP address"
                )
                return False

        if self.server != None:
            print("Connection already established")
            return True

        # Try to connect to the server and send a handshake
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.server.connect((self.address, self.port))
            self.server.send(self.__new_handshake())
        except socket.error as e:
            print(e)
            if e.args[0] == errno.ECONNREFUSED:
                print("Returned ECONNREFUSED ({}:{})".format(self.address, self.port))
            return False

        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # self.server.setblocking(0)
        self.inp = [self.server]
        self.out = []
        return True

    def __new_handshake(self, cursor=0, token=NULL_TOKEN):
        """Returns a new binary handshake message"""
        handshake = bytearray()
        handshake_contents = ubjson.dumpb(
            {
                "type": CommType.HANDSHAKE.value,
                "payload": {
                    "cursor": cursor,
                    "clientToken": token,
                    "isRealtime": self.realtime,
                },
            }
        )
        handshake += pack(">L", len(handshake_contents))
        handshake += handshake_contents
        return handshake


def get_sigint_handler(client):
    """Return a SIGINT handler for the provided SlippiCommClient object"""

    def handler(signum, stack):
        print("Caught SIGINT, stopping client")
        client.shutdown()
        exit(0)

    return handler
