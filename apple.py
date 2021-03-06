import random
import pygame
from constans import *


class Apple(pygame.sprite.Sprite):
    def __init__(self, position):
        super().__init__()
        self.surface = pygame.Surface((20, 20), pygame.SRCALPHA)
        self.rect = self.surface.get_rect(x=position[0] * SEGMENT_SIZE, y=position[1] * SEGMENT_SIZE)
        self.surface.blit(pygame.image.load("img/beer.png"), (0, 0))

    def draw(self, screen):
        screen.blit(self.surface, self.rect)
