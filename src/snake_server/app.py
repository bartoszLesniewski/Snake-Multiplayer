from __future__ import annotations

import asyncio
import logging
import os
import sys

log = logging.getLogger(__name__)


class App:
    def __init__(self) -> None:
        self.host = "127.0.0.1"
        self.port = 8888

    async def run(self) -> int:
        self.setup_logging()
        await self.run_server()

    async def close(self) -> None:
        ...

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
        log.info("Accepted a connection from %s:%s", conn.host, conn.port)
        writer.close()
        await writer.wait_closed()
