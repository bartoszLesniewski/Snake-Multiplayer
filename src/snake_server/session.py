from __future__ import annotations

import asyncio
import datetime
import itertools
import logging
import random
from collections import defaultdict, deque
from collections.abc import Collection, Generator
from typing import TYPE_CHECKING, Any

from .enums import Direction

if TYPE_CHECKING:
    from .app import App
    from .connection import Connection

log = logging.getLogger(__name__)


class SessionPlayer:
    def __init__(self, conn: Connection, name: str) -> None:
        self.conn = conn
        self.name = name
        self.alive = True
        self.chunks: deque[tuple[int, int]] = deque()
        self.direction = Direction.RIGHT

    @property
    def head(self) -> tuple[int, int]:
        return self.chunks[0]

    @property
    def tail(self) -> list[tuple[int, int]]:
        if not self.chunks:
            return []
        head, *tail = self.chunks
        return tail

    @property
    def key(self) -> str:
        return self.conn.key

    @property
    def session(self) -> str:
        return self.conn.session

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "chunks": [list(chunk) for chunk in self.chunks],
        }

    def __eq__(self, other: SessionPlayer) -> bool:
        return self.conn is other.conn

    def move(self) -> None:
        head_x, head_y = self.head
        offset_x, offset_y = self.direction.offset
        self.chunks.appendleft((head_x + offset_x, head_y + offset_y))

        for apple_pos in self.session.apples:
            if apple_pos == self.head:
                self.session.apples.remove(apple_pos)
                break
        else:
            self.chunks.pop()


class Session:
    def __init__(
        self, *, app: App, owner: Connection, owner_name: str, code: str
    ) -> None:
        self.app = app
        self.owner = SessionPlayer(owner, owner_name)
        self.code = code

        #: stores all players that were ever in the running session,
        #: regardless of whether they're still connected
        self.players: dict[str, SessionPlayer] = {self.owner.key: self.owner}
        #: stores alive (and still connected) players
        self.alive_players: dict[str, SessionPlayer] = self.players.copy()
        #: list of deaths ordered by death time (most recent death is the last entry)
        self.dead_players: list[SessionPlayer] = []
        self.apples: set[tuple[int, int]] = set()

        self.running = False
        self.task: asyncio.Task | None = None
        self.tick = 0
        #: this might be a time in the past or future
        self.last_tick_time = datetime.datetime.min

    def is_name_taken(self, name: str) -> bool:
        return any(player.name == name for player in self.players.values())

    async def start(self) -> None:
        self.running = True
        await asyncio.gather(
            *(
                player.conn.send_session_start(self)
                for player in self.alive_players.values()
            )
        )
        self.task = asyncio.create_task(self.run())
        self.task.add_done_callback(self._task_error_handler)

    def stop(self) -> None:
        if self.task is not None:
            self.task.cancel()
        self.running = False

    def _task_error_handler(self, task: asyncio.Task) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            log.error(
                "Unexpected error occurred while running session with code %r.",
                exc_info=exc,
            )

            self.running = False
            for player in self.players.values():
                player.conn.session = None
                asyncio.create_task(player.conn.close())
            asyncio.create_task(self.app.remove_session(self))

    def get_next_sleep_time(self) -> float:
        self.last_tick_time += self.app.tick_interval
        sleep_delta = self.last_tick_time - datetime.datetime.now(datetime.timezone.utc)
        ret = sleep_delta.total_seconds()
        if ret < 0:
            log.warning("Session %r is behind!", self.code)
        return ret

    def get_state(self) -> dict[str, Any]:
        return {
            "tick": self.tick,
            "apples": [list(apple_pos) for apple_pos in self.apples],
            "alive_players": [
                player.to_dict() for player in self.alive_players.values()
            ],
        }

    async def run(self) -> None:
        self.last_tick_time = datetime.datetime.now(datetime.timezone.utc)
        while True:
            self.tick += 1

            if self.update_positions():
                self.handle_wall_deaths()
                self.handle_tail_self_cutting()
                self.handle_collision_deaths()

            self.generate_apples()

            # broadcast the state update to all connections
            state = self.get_state()
            await asyncio.gather(
                *(
                    player.conn.send_session_state_update(self, state)
                    for player in self.players.values()
                )
            )

            # sleep until next tick
            await asyncio.sleep(self.get_next_sleep_time())

    def update_positions(self) -> bool:
        if self.tick % self.app.game_speed:
            return False

        for player in self.alive_players.values():
            player.move()

        return True

    def handle_wall_deaths(self) -> None:
        to_remove: list[str] = []
        for player in self.alive_players.values():
            x, y = player.head
            if x < 0 or x >= self.app.grid_width or y < 0 or y >= self.app.grid_height:
                to_remove.append(player.key)
        for key in to_remove:
            self.dead_players[key] = self.alive_players.pop(key)

    def handle_tail_self_cutting(self) -> None:
        """Handle a collision with your own tail by cutting it in that spot."""
        for player in self.alive_players.values():
            try:
                idx = player.chunks.index(player.head, 1)
            except ValueError:
                pass
            else:
                for _ in range(len(player.chunks) - idx):
                    player.chunks.pop()

    def handle_collision_deaths(self) -> None:
        self.handle_tail_collisions()
        self.handle_head_overlap_collisions()
        self.handle_head_on_collisions()

    def handle_tail_collisions(self) -> None:
        """
        Handle 'tail collisions'.

        Collision description:
            Player 1's head overlaps player 2's tail or they both overlap
            each other's tails.

        Examples:
            1. Player 1's head overlaps player 2's tail.
                - Before collision:
                    --->
                      ^
                      |

                - After collision:
                     -^->
                      |

            2. Player 1's head overlaps player 2's tail
               *and* player 2's head overlaps player 1's tail.
                - Before collision:
                      |
                      |
                    +>|
                    |<+
                    |
                    |

                - After collision 2:
                      |
                    +->
                    <-+
                    |

        Condition:
            p1.head in p2.tail AND (p1, p2) are not head overlap or head-on colliding

        Result:
            Death of the player whose head is in other player's tail.
            If both of the heads are in each other's tails, choose randomly.
        """
        deaths: set[str] = set()
        for p1, p2 in itertools.combinations(self.alive_players.values(), 2):
            if p1.key in deaths or p2.key in deaths:
                continue
            if (
                # head overlap collision
                p1.head != p2.head
                # head-on collision
                and (p1.chunks[0] != p2.chunks[1] and p2.chunks[0] != p1.chunks[1])
            ):
                potential_losers = []
                if p1.head in p2.chunks:
                    potential_losers.append(p1)
                if p2.head in p1.chunks:
                    potential_losers.append(p2)
                deaths.update(choose_losers(potential_losers))

        for key in deaths:
            self.dead_players[loser.key] = self.alive_players.pop(loser.key)

    def handle_head_overlap_collisions(self) -> None:
        """
        Handle 'head overlap collisions'.

        Collision description:
            Heads overlap.

        Example:
            - Before collision:
                ---> <---

            - After collision:
                 ---X---

        Condition:
            p1.head == p2.head

        Result:
            Death of the shorter player. For players of same length, choose randomly.
        """
        overlapping_heads: defaultdict[
            tuple[int, int], list[SessionPlayer]
        ] = defaultdict(list)
        for player in self.alive_players.values():
            overlapping_heads[player.head].append(player)

        for players in overlapping_heads.values():
            if len(players) > 1:
                for key in choose_losers(players):
                    self.dead_players[key] = self.alive_players.pop(key)

    def handle_head_on_collisions(self) -> None:
        """
        Handle 'head-on collisions'.

        Collision description:
            Heads overlap with the first tail element of their opponent.
            This can only happen when two players drove at each other
            from opposite directions.

        Example:
            - Before collision:
                ---><---

            - After collision:
                ---<>---

        Condition:
            p1.head == p2.chunks[1] AND p2.head == p1.chunks[1]

        Result:
            Death of the shorter player. For players of same length, choose randomly.
        """
        deaths: set[str] = set()
        for p1, p2 in itertools.combinations(self.alive_players.values(), 2):
            if p1.key in deaths or p2.key in deaths:
                continue
            if p1.chunks[0] == p2.chunks[1] and p2.chunks[0] == p1.chunks[1]:
                deaths.update(choose_losers((p1, p2)))

        for key in deaths:
            self.dead_players[key] = self.alive_players.pop(key)

    def generate_apples(self) -> None:
        # for now, there can only be one apple in the game
        if self.apples:
            return

        taken_positions = set()
        for player in self.alive_players.values():
            taken_positions.update(player.chunks)
        taken_positions.update(self.apples)

        while True:
            apple_pos = (
                random.randrange(self.app.grid_width),
                random.randrange(self.app.grid_height),
            )
            if apple_pos not in taken_positions:
                break

        self.apples.add(apple_pos)

    async def connect(self, connection: Connection, name: str) -> None:
        if self.running:
            raise RuntimeError("Can't connect while the game is running.")
        player = SessionPlayer(connection, name)
        self.players[player.key] = player
        self.alive_players[player.key] = player
        await asyncio.gather(
            *(
                player.conn.send_session_join(self, player)
                for player in self.alive_players.values()
            )
        )

    async def disconnect(self, connection: Connection) -> None:
        if not self.running:
            del self.players[connection.key]

        try:
            player = self.alive_players.pop(connection.key)
        except KeyError:
            if self.running and connection.key in self.players:
                log.warning(
                    "disconnect() called for connection that is no longer"
                    " in the session."
                )
            else:
                # tried to disconnect a player that is not part of the session
                raise
        else:
            player.alive = False
            self.dead_players.append(player)

        if self.alive_players:
            if self.owner == player:
                self.owner = next(iter(self.alive_players.values()))
            await asyncio.gather(
                *(
                    player.conn.send_session_leave(self, connection.key)
                    for player in self.alive_players.values()
                )
            )
        else:
            self.stop()
            await self.app.remove_session(self)

        await connection.send_session_leave(self, connection.key)
        if self.running and len(self.alive_players) == 1:
            self.dead_players.append(self.owner)
            await self.owner.send_session_end(self)
            await self.app.remove_session(self)


def choose_losers(players: Collection[SessionPlayer]) -> Generator[str, None, None]:
    if not players:
        return

    m = max(players, key=lambda p: len(p.chunks))
    winner = random.choice([p for p in players if len(p.chunks) == m])
    for player in players:
        if player != winner:
            yield player.key
