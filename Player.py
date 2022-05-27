from Connection import Connection
from Snake import Snake
from constans import *


class Player:
    def __init__(self, name):
        self.snake = Snake(WIDTH / 2, HEIGHT / 2)
        self.name = name
        self.connection = Connection()
