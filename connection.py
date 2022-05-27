import json
import socket


class Connection:
    def __init__(self, server_address="127.0.0.1", server_port=8888):
        self.server_address = server_address
        self.server_port = server_port
        self.session_code = "a@wQ"
        self.player_key = None
        self.socket = socket.socket()
        self.writer = None
        self.reader = None

    def connect(self):
        self.socket.connect((self.server_address, self.server_port))
        sockname = self.socket.getsockname()
        self.player_key = str(sockname[0]) + ":" + str(sockname[1])
        self.writer = self.socket.makefile("wb")
        self.reader = self.socket.makefile("r")

    def create_sesssion(self):
        ...


#    def send_message(self, msg_type, data)
#        serialized = json.dumps(
#            {"type": msg_type.value, "data": data}, separators=(",", ":")
#        )
#        self.writer.write(f"{serialized}\n".encode())
#        await self.writer.drain()

