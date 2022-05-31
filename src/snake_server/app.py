from __future__ import annotations

import asyncio
import configparser
import datetime
import logging
import os
import sys

from .connection import Connection
from .session import Session
from .utils import generate_invite_code

log = logging.getLogger(__name__)

CONFIG_SECTION_NAME = "snake_server"


def config_get(config: configparser.ConfigParser, option: str) -> str:
    return config.get(CONFIG_SECTION_NAME, option)


def config_getint(
    config: configparser.ConfigParser,
    option: str,
    *,
    fallback: int | None = None,
) -> int:
    try:
        raw_value = config.get(CONFIG_SECTION_NAME, option)
    except (configparser.NoSectionError, configparser.NoOptionError):
        if fallback is not None:
            return fallback
        raise

    try:
        return int(raw_value)
    except ValueError:
        raise ValueError(option)


class App:
    def __init__(self) -> None:
        self.host = "127.0.0.1"
        self.port = 8888
        self.tick_interval = datetime.timedelta(milliseconds=50)
        #: players move once every `game_speed` ticks
        self.game_speed = 1
        self.grid_width = 40
        self.grid_height = 30
        self.initial_chunk_amount = 4
        self.sessions: dict[str, Session] = {}
        self.sessions_lock = asyncio.Lock()
        self.connections: dict[str, Connection] = {}

    async def run(self) -> int:
        self.setup_logging()
        try:
            self.load_config()
        except (configparser.NoSectionError, configparser.NoOptionError) as exc:
            log.error(
                "Failed to load configuration file (snake_server_config.ini): %s", exc
            )
            return 2
        except ValueError:
            return 2
        except FileNotFoundError:
            log.error(
                "A configuration file snake_server_config.ini does not exist"
                " in the current directory. You can see an example configuration in"
                " snake_server_config.ini.example file."
            )
            return 2
        await self.run_server()
        return 0

    async def close(self) -> None:
        async with self.sessions_lock:
            for session in self.sessions.values():
                session.stop()
            self.sessions.clear()

        for conn in list(self.connections.values()):
            await conn.close()
        self.connections.clear()

    def setup_logging(self) -> None:
        if os.path.exists("latest.log"):
            os.replace("latest.log", "previous.log")

        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        file_handler = logging.FileHandler("latest.log")
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s", datefmt="%X"
        )
        file_handler.setFormatter(formatter)

        root_logger.addHandler(file_handler)
        if sys.stderr is not None:
            stream_handler = logging.StreamHandler(sys.stderr)
            root_logger.addHandler(stream_handler)

    def load_config(self) -> None:
        config = configparser.ConfigParser()
        with open("snake_server_config.ini") as fp:
            config.read_file(fp)

        self.host = config_get(config, "host")
        try:
            self.port = config_getint(config, "port")
            self.tick_interval = datetime.timedelta(
                milliseconds=config_getint(config, "tick_interval", fallback=50)
            )
            self.game_speed = config_getint(
                config, "game_speed", fallback=self.game_speed
            )
            self.initial_chunk_amount = config_getint(
                config, "initial_chunk_amount", fallback=self.initial_chunk_amount
            )
        except ValueError as exc:
            log.error(
                "Expected an integer for %r key in the configuration file.", exc.args[0]
            )
            raise

    async def run_server(self) -> int:
        log.info("Starting a socket server on %s:%s...", self.host, self.port)
        server = await asyncio.start_server(self.socket_handler, self.host, self.port)
        log.info("Socket server started.")

        async with server:
            await server.serve_forever()

        log.info("Socket server stopped.")

        return 0

    async def socket_handler(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        conn = Connection(self, reader, writer)
        self.connections[conn.key] = conn
        log.info("Accepted a connection from %s:%s", conn.host, conn.port)
        await conn.run()

    async def create_session(self, owner: Connection, owner_name: str) -> Session:
        invite_code = ""
        async with self.sessions_lock:
            for _ in range(5):
                invite_code = generate_invite_code()
                if invite_code not in self.sessions:
                    break
            else:
                raise RuntimeError(
                    "Failed to generate unique invite code for the session."
                )

            session = Session(
                app=self,
                owner=owner,
                owner_name=owner_name,
                code=invite_code,
            )
            self.sessions[invite_code] = session

        await owner.send_session_join(session, session.owner)
        return session

    async def remove_session(self, session: Session) -> None:
        async with self.sessions_lock:
            self.sessions.pop(session.code, None)
            log.info("Session with code %r ended.", session.code)
