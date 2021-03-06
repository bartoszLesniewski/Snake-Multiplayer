from snake import Snake
from constans import *


class Player:
    def __init__(self, name, key=None):
        self.snake = Snake(WIDTH / 2, HEIGHT / 2)
        self.name = name
        # self.connection = Connection(key)
        self.key = key
        self.is_alive = True

    @property
    def check_if_alive(self):
        return self.is_alive
