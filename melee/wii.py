from socket import *
from struct import unpack

import ubjson

from melee import enums
from melee.console import Console
from melee.gamestate import GameState
from melee.slippstream import CommType, EventType, SlippstreamClient


class Wii:
    def __init__(self, ai_port, opponent_port, opponent_type, logger=None):
        self.logger = logger
        self.ai_port = ai_port
        self.opponent_port = opponent_port

        self.processingtime = 0
        self.slippi_address = ""
        self.slippi_port = 51441

        self.eventsize = [0] * 0x100

    def run(self):
        """Connects to the Slippi/Wii.

        Returns boolean of success"""
        # TODO: Connect to the Slippi networking port
        self.slippstream = SlippstreamClient(self.slippi_address, self.slippi_port)
        return self.slippstream.connect()

    def stop(self):
        # TODO: Disconnect cleanly from Slippi networking port
        pass

    def step(self):
        # TODO: Actually get a real gamestate from the console

        # Keep looping until we get a REPLAY message
        # TODO: This might still not be all we need. Verify the frame ends here
        gamestate = GameState(self.ai_port, self.opponent_port)
        while True:
            msg = self.slippstream.read_message()
            if msg:
                if CommType(msg["type"]) == CommType.REPLAY:
                    events = msg["payload"]["data"]
                    self.__handle_slippstream_events(events, gamestate)
                    # TODO: Fix frame indexing and iasa
                    return gamestate

                # We can basically just ignore keepalives
                elif CommType(msg["type"]) == CommType.KEEPALIVE:
                    print("Keepalive")
                    continue

                elif CommType(msg["type"]) == CommType.HANDSHAKE:
                    p = msg["payload"]
                    print(
                        "Connected to console '{}' (Slippi Nintendont {})".format(
                            p["nick"],
                            p["nintendontVersion"],
                        )
                    )
                    continue

    def __handle_slippstream_events(self, event_bytes, gamestate):
        """Handle a series of events, provided sequentially in a byte array"""
        while len(event_bytes) > 0:
            event_size = self.eventsize[event_bytes[0]]
            if len(event_bytes) < event_size:
                print(
                    "WARNING: Something went wrong unpacking events. Data is probably missing"
                )
                print("\tDidn't have enough data for event")
                return

            if EventType(event_bytes[0]) == EventType.PAYLOADS:
                cursor = 0x2
                payload_size = event_bytes[1]
                num_commands = (payload_size - 1) // 3
                for i in range(0, num_commands):
                    command, command_len = unpack(
                        ">bH", event_bytes[cursor : cursor + 3]
                    )
                    self.eventsize[command] = command_len + 1
                    cursor += 3
                event_bytes = event_bytes[payload_size + 1 :]
                continue

            elif EventType(event_bytes[0]) == EventType.FRAME_START:
                self.frame_num = unpack(">i", event_bytes[1:5])[0]
                event_bytes = event_bytes[event_size:]
                continue

            elif EventType(event_bytes[0]) == EventType.GAME_START:
                event_bytes = event_bytes[event_size:]
                continue

            elif EventType(event_bytes[0]) == EventType.GAME_END:
                event_bytes = event_bytes[event_size:]
                continue

            elif EventType(event_bytes[0]) == EventType.PRE_FRAME:
                event_bytes = event_bytes[event_size:]
                continue

            elif EventType(event_bytes[0]) == EventType.POST_FRAME:
                gamestate.frame = unpack(">i", event_bytes[0x1 : 0x1 + 4])[0]
                controller_port = unpack(">B", event_bytes[0x5 : 0x5 + 1])[0] + 1

                gamestate.player[controller_port].x = unpack(
                    ">f", event_bytes[0xA : 0xA + 4]
                )[0]
                gamestate.player[controller_port].y = unpack(
                    ">f", event_bytes[0xE : 0xE + 4]
                )[0]

                gamestate.player[controller_port].character = enums.Character(
                    unpack(">B", event_bytes[0x7 : 0x7 + 1])[0]
                )
                try:
                    gamestate.player[controller_port].action = enums.Action(
                        unpack(">H", event_bytes[0x8 : 0x8 + 2])[0]
                    )
                except ValueError:
                    gamestate.player[controller_port].action = (
                        enums.Action.UNKNOWN_ANIMATION
                    )

                # Melee stores this in a float for no good reason. So we have to convert
                facing_float = unpack(">f", event_bytes[0x12 : 0x12 + 4])[0]
                gamestate.player[controller_port].facing = facing_float > 0

                gamestate.player[controller_port].percent = int(
                    unpack(">f", event_bytes[0x16 : 0x16 + 4])[0]
                )
                gamestate.player[controller_port].stock = unpack(
                    ">B", event_bytes[0x21 : 0x21 + 1]
                )[0]
                gamestate.player[controller_port].action_frame = int(
                    unpack(">f", event_bytes[0x22 : 0x22 + 4])[0]
                )

                # Extract the bit at mask 0x20
                bitflags2 = unpack(">B", event_bytes[0x27 : 0x27 + 1])[0]
                gamestate.player[controller_port].hitlag = bool(bitflags2 & 0x20)

                gamestate.player[controller_port].hitstun_frames_left = int(
                    unpack(">f", event_bytes[0x2B : 0x2B + 4])[0]
                )
                gamestate.player[controller_port].on_ground = not bool(
                    unpack(">B", event_bytes[0x2F : 0x2F + 1])[0]
                )
                gamestate.player[controller_port].jumps_left = unpack(
                    ">B", event_bytes[0x32 : 0x32 + 1]
                )[0]

                event_bytes = event_bytes[event_size:]
                continue

            elif EventType(event_bytes[0]) == EventType.GECKO_CODES:
                event_bytes = event_bytes[event_size:]
                continue

            elif EventType(event_bytes[0]) == EventType.FRAME_BOOKEND:
                event_bytes = event_bytes[event_size:]
                continue

            elif EventType(event_bytes[0]) == EventType.ITEM_UPDATE:
                # TODO projectiles
                event_bytes = event_bytes[event_size:]
                continue

            else:
                print(
                    "WARNING: Something went wrong unpacking events. "
                    + "Data is probably missing"
                )
                print("\tGot invalid event type: ", event_bytes[0])
                return

        return
