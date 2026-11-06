from dataclasses import dataclass
from bs4 import Tag


@dataclass
class Track:
    event: str
    num: str
    artists: str
    team: str
    title: str
    size: str
    addr: Tag
