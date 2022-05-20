import random
import pygame
from constans import *


class Apple(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        x_position, y_position = self.rand_position()
        self.surface = pygame.Surface((20, 20), pygame.SRCALPHA)
        self.rect = self.surface.get_rect(x=x_position, y=y_position)
        self.surface.blit(pygame.image.load("img/beer.png"), (0, 0))

    @staticmethod
    def rand_position():
        x = random.randint(1, WIDTH/SEGMENT_SIZE) * SEGMENT_SIZE
        y = random.randint(1, HEIGHT/SEGMENT_SIZE) * SEGMENT_SIZE

        return x, y

    def draw(self, screen):
        screen.blit(self.surface, self.rect)
