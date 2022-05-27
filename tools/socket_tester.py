"""
This is a helper tool for development of the snake_server
while the connection logic is not implemented on the client side.
"""

import getpass
import json
import socket
import threading
from pprint import pprint


class App:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.sock = socket.socket()
        self.input_thread = None

    def run(self) -> None:
        sock = self.sock
        try:
            sock.connect(("127.0.0.1", 8888))
            print("Accepting messages from 127.0.0.1:8888")
            with sock.makefile("w") as self.writer, sock.makefile("r") as self.reader:
                self.input_thread = threading.Thread(
                    target=self.wait_for_input, daemon=True
                )
                self.input_thread.start()
                self.read_messages()
        except KeyboardInterrupt:
            if not self.closing:
                print("Ctrl+C received, exiting...")
        finally:
            sock.close()

    def read_messages(self) -> None:
        while True:
            try:
                line = self.reader.readline()
            except BrokenPipeError:
                break
            if not line:
                break
            with self.lock:
                pprint(json.loads(line), sort_dicts=False)

        print("SOCKET CLOSED")

    def wait_for_input(self) -> None:
        try:
            PROMPT = (
                "\x1b[32m"
                "Hit Enter to pause reader thread and send message"
                " or hit Q and Enter to quit."
                "\x1b[0m"
            )
            print(PROMPT)
            while True:
                command = getpass.getpass("")
                if command == "q":
                    self.closing = True
                    self.sock.shutdown(socket.SHUT_RDWR)
                    break

                with self.lock:
                    payload = input("Provide json payload:\n")
                    try:
                        payload = json.dumps(json.loads(payload), separators=(",", ":"))
                    except json.JSONDecodeError:
                        print("INVALID JSON PAYLOAD")
                    else:
                        self.writer.write(f"{payload}\n")
                        self.writer.flush()
                        print("MESSAGE SENT")
                    print(PROMPT)
        except (KeyboardInterrupt, EOFError):
            print("Ctrl+C received, exiting...")
            self.closing = True
            self.sock.shutdown(socket.SHUT_RDWR)


if __name__ == "__main__":
    app = App()
    app.run()
