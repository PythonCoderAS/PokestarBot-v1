import enum


class BracketStatus(enum.IntFlag):
    OPEN = 1
    VOTABLE = 2
    DEFAULT = 3
    CLOSED = 4
    LOCKED = 8
    ALL = OPEN | VOTABLE | CLOSED | LOCKED
