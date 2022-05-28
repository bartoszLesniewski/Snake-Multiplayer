from connection import Connection
from snake import Snake
from constans import *


class Player:
    def __init__(self, name, key=None):
        self.snake = Snake(WIDTH / 2, HEIGHT / 2)
        self.name = name
        # self.connection = Connection(key)
        self.key = key
