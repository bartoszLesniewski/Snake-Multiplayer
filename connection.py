import json
import select
import socket

from messages import Message


class Connection:
    def __init__(self, server_address="127.0.0.1", server_port=8888):
        self.server_address = server_address
        self.server_port = server_port
        self.session_code = None
        # self.player_key = key
        self.socket = socket.socket()
        self.writer = None
        self.reader = None

    def connect(self):
        self.socket.connect((self.server_address, self.server_port))
        sockname = self.socket.getsockname()
        player_key = str(sockname[0]) + ":" + str(sockname[1])
        self.writer = self.socket.makefile("wb")
        self.reader = self.socket.makefile("rb")

        return player_key

    def create_session(self, player_name):
        data = {"player_name": player_name}
        self.send_message(Message.CREATE_SESSION, data)
        msg = self.receive_message()
        self.session_code = msg["data"]["code"]
        # self.send_message(Message.START_SESSION, data)
        # self.receive_message()

    def send_message(self, msg_type, data):
        msg = json.dumps(
            {"type": msg_type.value, "data": data}, separators=(",", ":")
        )

        self.writer.write(f"{msg}\n".encode())
        self.writer.flush()

    def receive_message(self):
        response = self.reader.readline().decode()
        print(response)
        msg = json.loads(response)

        return msg

    def check_for_message(self):
        response, _, _ = select.select([self.socket], [], [], 0.0001)
        if response:
            line = self.reader.readline().decode()
            print("MESASGE FROM SERVER: " + line)
            msg = json.loads(line)
            # print(msg)
            if msg["type"] == Message.SESSION_JOIN.value:
                players = msg["data"]["players"]
                return Message.SESSION_JOIN, players
            elif msg["type"] == Message.SESSION_LEAVE.value:
                return Message.SESSION_LEAVE, msg["data"]
            elif msg["type"] == Message.SESSION_START.value:
                return Message.SESSION_START, None
            elif msg["type"] == Message.SESSION_STATE_UPDATE.value:
                return Message.SESSION_STATE_UPDATE, msg["data"]
            else:
                return None, None
        else:
            # print("No message")
            return None

    def join_session(self, player_name, code):
        data = {"code": code, "player_name": player_name}
        self.send_message(Message.JOIN_SESSION, data)
        msg = self.receive_message()
        self.session_code = msg["data"]["code"]

        return msg["data"]

    def start_session(self, player_name, code):
        data = {"code": code, "player_name": player_name}
        self.send_message(Message.START_SESSION, data)
        msg = self.receive_message()
