import pygame

from direction import Direction
from segment import Segment
from constans import *


class Snake (pygame.sprite.Sprite):
    def __init__(self, x_start, y_start):
        super().__init__()
        self.head = self.create_head(x_start, y_start)
        self.segments = []
        self.segments.append(self.head)
        self.direction = Direction.UP

    def update_segments(self, chunks, direction):
        self.segments.clear()
        for segment in chunks:
            self.segments.append(Segment(segment[0] * SEGMENT_SIZE, segment[1] * SEGMENT_SIZE))

        self.head = self.create_head(chunks[0][0] * SEGMENT_SIZE, chunks[0][1] * SEGMENT_SIZE)
        self.segments[0] = self.head

        self.direction = Direction(direction).name

    @staticmethod
    def create_head(x, y):
        head = Segment(x, y)
        head.surface.blit(pygame.image.load("img/head.png"), (0, 0))
        return head

    def draw(self, screen):
        for segment in self.segments:
            screen.blit(segment.surface, segment.rect)
